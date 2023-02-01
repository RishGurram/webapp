# Python Imports
import json
import base64

# Framework Imports
from fastapi import FastAPI, Depends, Header
from fastapi import status
from passlib.context import CryptContext
from sqlalchemy.orm import Session

# Project Imports
import models
from database import get_db
from schema import User, LoginSerializer
from utils import response

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()


@app.post("/v1/user")
def create_user(user: User, db: Session = Depends(get_db)):
    try:
        existing_user = db.query(models.User).filter_by(email=user.email).first()
        if existing_user:
            return response(False, "User with this email already exists", status.HTTP_400_BAD_REQUEST)

        new_user = models.User(email=user.email,
                               first_name=user.first_name,
                               last_name=user.last_name,
                               password=pwd_context.encrypt(user.password))

        db.add(new_user)
        db.commit()
        return_data = json.loads(
            json.dumps(db.query(models.User).filter_by(email=user.email).first().to_dict(),
                       indent=4, sort_keys=True, default=str))
        return response(True, "User Created Successfully", status.HTTP_201_CREATED, return_data)
    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)


def authenticate_user(user: LoginSerializer, db: Session = Depends(get_db)):
    try:
        if not user.email or not user.password:
            return response(False, "Email and password are required", status.HTTP_400_BAD_REQUEST)

        stored_user = db.query(models.User).filter_by(email=user.email).first()
        if not stored_user:
            return response(False, "Incorrect email or password", status.HTTP_401_UNAUTHORIZED)

        if not pwd_context.verify(user.password, stored_user.password):
            return response(False, "Incorrect email or password", status.HTTP_401_UNAUTHORIZED)

        # generate token
        token = base64.b64encode(
            f'{user.email}:{user.password}'.encode()).decode()

        # return response with token and user data
        return response(True, "Login Successful", status.HTTP_200_OK, data={
            "first_name": stored_user.first_name,
            "last_name": stored_user.last_name,
            "email": stored_user.email
        }, headers={
            "access-token": token
        })
    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)


@app.post("/v1/user/login")
def login(user: LoginSerializer, auth: str = Depends(authenticate_user)):
    return auth


@app.get("/v1/user/{user_id}")
async def get_user(user_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        # Check if user exists
        user = db.query(models.User).filter_by(id=user_id).first()
        if not user:
            return response(False, "User not found", status.HTTP_404_NOT_FOUND)

        if authorization is None:
            return response(False, "Authorization header missing", status.HTTP_400_BAD_REQUEST)
        try:
            auth_type, encoded_code = authorization.split(" ")
            if auth_type != "Basic":
                return response(False, "Authorization type not supported", status.HTTP_400_BAD_REQUEST)

            code = base64.b64decode(encoded_code).decode("utf-8")
            email, password = code.split(":")

            if not pwd_context.verify(password, user.password):
                return response(False, "Invalid authorization", status.HTTP_401_UNAUTHORIZED)

            # Check if user is authorized to access this data
            if user.email != email:
                return response(False, "Not authorized to access other user's data", status.HTTP_403_FORBIDDEN)

            return response(True, "User data fetched successfully",
                            status.HTTP_200_OK, data=json.loads(json.dumps(user.to_dict(),
                                                                           indent=4, sort_keys=True, default=str)))
        except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)


@app.put("/v1/user/{user_id}")
async def update_user(user_id: int, data: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        # Check if user exists
        user = db.query(models.User).filter_by(id=user_id).first()
        if not user:
            return response(False, "User not found", status.HTTP_404_NOT_FOUND)

        if authorization is None:
            return response(False, "Authorization header missing", status.HTTP_400_BAD_REQUEST)
        try:
            auth_type, encoded_code = authorization.split(" ")
            if auth_type != "Basic":
                return response(False, "Authorization type not supported", status.HTTP_400_BAD_REQUEST)

            code = base64.b64decode(encoded_code).decode("utf-8")
            email, password = code.split(":")

            if not pwd_context.verify(password, user.password):
                return response(False, "Invalid authorization", status.HTTP_401_UNAUTHORIZED)

            # Check if user is authorized to access this data
            if user.email != email:
                return response(False, "Not authorized to access other user's data", status.HTTP_403_FORBIDDEN)

            # Update user data
            user.first_name = data.get("first_name", user.first_name)
            user.last_name = data.get("last_name", user.last_name)
            user.password = pwd_context.encrypt(data.get("password")) if data.get("password", None) else user.password

            db.add(user)
            db.commit()
            db.refresh(user)

            return response(True, "User data Updated successfully",
                            status.HTTP_200_OK, data=json.loads(json.dumps(user.to_dict(),
                                                                           indent=4, sort_keys=True, default=str)))
        except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)


@app.get("/healthz/")
async def health_check():
    return response(True, "Health check successful", status.HTTP_200_OK)
