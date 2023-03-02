# Python Imports
import boto3
import json
import base64
import os
import uuid

# Framework Imports
from fastapi import FastAPI, Depends, Header, HTTPException, Request, File, UploadFile
from fastapi import status
from fastapi.exceptions import RequestValidationError
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from fastapi.responses import JSONResponse
from typing import List
from fastapi.encoders import jsonable_encoder

# Project Imports
import models, schema
from database import get_db, engine
from schema import User, LoginSerializer, Product, CustomException
from utils import response
from datetime import datetime

models.Base.metadata.create_all(bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()

@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    dct = {}
    for error in exc.errors():
        dct[error["loc"][1]] = error["msg"]

    return JSONResponse(
        status_code=status.HTTP_400_BAD_REQUEST,
        content=dct,
    )

@app.exception_handler(CustomException)
async def handle_custom_exception(request, exc: CustomException):
    return JSONResponse(
        status_code=exc.status_code, content=exc.msg
    )


@app.post("/v1/user")
def create_user(user: User, db: Session = Depends(get_db)):
    try:
        existing_user = db.query(models.User).filter_by(username=user.username).first()
        if existing_user:
            return response(False, "User with this username already exists", status.HTTP_400_BAD_REQUEST)

        new_user = models.User(username=user.username,
                               first_name=user.first_name,
                               last_name=user.last_name,
                               password=pwd_context.encrypt(user.password)
                               )

        db.add(new_user)
        db.commit()
        return_data = json.loads(
            json.dumps(db.query(models.User).filter_by(username=user.username).first().to_dict(),
                       indent=4, sort_keys=True, default=str))
        return response(True, "User Created Successfully", status.HTTP_201_CREATED, return_data)
    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)



def authenticate_user(user: LoginSerializer, db: Session = Depends(get_db)):
    try:
        if not user.username or not user.password:
            return response(False, "Username and password are required", status.HTTP_400_BAD_REQUEST)

        stored_user = db.query(models.User).filter_by(username=user.username).first()
        if not stored_user:
            return response(False, "Incorrect username or password", status.HTTP_401_UNAUTHORIZED)

        if not pwd_context.verify(user.password, stored_user.password):
            return response(False, "Incorrect username or password", status.HTTP_401_UNAUTHORIZED)

        # generate token
        token = base64.b64encode(
            f'{user.username}:{user.password}'.encode()).decode()

        # return response with token and user data
        return response(True, "Login Successful", status.HTTP_200_OK, data={
            "first_name": stored_user.first_name,
            "last_name": stored_user.last_name,
            "username": stored_user.username
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
            username, password = code.split(":")

            # Check if user is authorized to access this data
            if user.username != username:
                return response(False, "Not authorized to access other user's data", status.HTTP_403_FORBIDDEN)

            if not pwd_context.verify(password, user.password):
                return response(False, "Invalid authorization", status.HTTP_401_UNAUTHORIZED)

            

            return response(True, "User data fetched successfully",
                            status.HTTP_200_OK, data=json.loads(json.dumps(user.to_dict(),
                                                                           indent=4, sort_keys=True, default=str)))
        except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)


@app.put("/v1/user/{user_id}", response_class=JSONResponse)
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
            username, password = code.split(":")

            # Check if user is authorized to access this data
            if user.username != username:
                return response(False, "Not authorized to access other user's data", status.HTTP_403_FORBIDDEN)

            if not pwd_context.verify(password, user.password):
                return response(False, "Invalid authorization", status.HTTP_401_UNAUTHORIZED)

            # Update user data
            user.first_name = data.get("first_name", user.first_name)
            user.last_name = data.get("last_name", user.last_name)
            user.password = pwd_context.encrypt(data.get("password")) if data.get("password", None) else user.password

            db.add(user)
            db.commit()
            db.refresh(user)

            return response(True, "User Updated successfully", status.HTTP_204_NO_CONTENT)

            
        except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)



@app.get("/healthz/")
async def health_check():
    return response(True, "Health check successful", status.HTTP_200_OK)



@app.post("/v1/product")
def create_product(product: Product, authorization: str = Header(None),  db: Session = Depends(get_db)):
    try:

        if product.quantity < 0 or product.quantity > 100:
            return response(False, "Product quantity should be a positive integer", status.HTTP_400_BAD_REQUEST)

        existing_product = db.query(models.Product).filter_by(sku=product.sku).first()
        if existing_product:
            return response(False, "Product with this SKU already exists", status.HTTP_400_BAD_REQUEST)

        if authorization is None:
            return response(False, "Authorization header missing", status.HTTP_400_BAD_REQUEST)

        auth_type, encoded_code = authorization.split(" ")
        if auth_type != "Basic":
                return response(False, "Authorization type not supported", status.HTTP_400_BAD_REQUEST)

        code = base64.b64decode(encoded_code).decode("utf-8")

        username, password = code.split(":")

        user = db.query(models.User).filter_by(username=username).first()
        if not user:
            return response(False, "User not found", status.HTTP_404_NOT_FOUND)

        existing_product = db.query(models.Product).filter_by(sku=product.sku).first()
        if existing_product:
            return response(False, "Product with this SKU already exists", status.HTTP_400_BAD_REQUEST)


        new_product = models.Product(
            sku=product.sku,
            name=product.name,
            description=product.description,
            manufacturer=product.manufacturer,
            quantity=product.quantity,
            owner_user_id=user.id
        )

        db.add(new_product)
        db.commit()
        return_data = json.loads(
            json.dumps(db.query(models.Product).filter_by(sku=product.sku).first().to_dict(),
                       indent=4, sort_keys=True, default=str))
        return response(True, "Product Created Successfully", status.HTTP_201_CREATED, return_data)
    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)



@app.put("/v1/product/{product_id}")
async def update_product(product_id: int, data: Product, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:

        
        # Check if product exists
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            return response(False, "Product not found", status.HTTP_404_NOT_FOUND)

        if authorization is None:
            return response(False, "Authorization header missing", status.HTTP_400_BAD_REQUEST)
        try:
            auth_type, encoded_code = authorization.split(" ")
            if auth_type != "Basic":
                return response(False, "Authorization type not supported", status.HTTP_400_BAD_REQUEST)

            code = base64.b64decode(encoded_code).decode("utf-8")
            username, password = code.split(":")

            user = db.query(models.User).filter_by(username=username).first()
            if not user:
                return response(False, "User not found", status.HTTP_404_NOT_FOUND)
            
             # Check if user is authorized to access this data
            if product.owner_user_id != user.id:
                return response(False, "Not authorized to access other user's data", status.HTTP_403_FORBIDDEN)

            if not pwd_context.verify(password, user.password):
                return response(False, "Invalid authorization", status.HTTP_401_UNAUTHORIZED)

            if data.sku != product.sku:
                existing_product = db.query(models.Product).filter_by(sku=data.sku).first()
                if existing_product:
                    return response(False, "Product with this SKU already exists", status.HTTP_400_BAD_REQUEST)

           

            # Update product data
            product.name = data.name
            product.description = data.description
            product.sku = data.sku
            product.manufacturer = data.manufacturer
            product.quantity = data.quantity

            db.add(product)
            db.commit()
            db.refresh(product)

            return response(True, "Product Updated successfully", status.HTTP_204_NO_CONTENT)

            
        except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)

@app.patch("/v1/product/{product_id}")
async def update_product(product_id: int, data: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:

        
        # Check if product exists
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            return response(False, "Product not found", status.HTTP_404_NOT_FOUND)

        if authorization is None:
            return response(False, "Authorization header missing", status.HTTP_400_BAD_REQUEST)
        try:
            auth_type, encoded_code = authorization.split(" ")
            if auth_type != "Basic":
                return response(False, "Authorization type not supported", status.HTTP_400_BAD_REQUEST)

            code = base64.b64decode(encoded_code).decode("utf-8")
            username, password = code.split(":")

            user = db.query(models.User).filter_by(username=username).first()
            if not user:
                return response(False, "User not found", status.HTTP_404_NOT_FOUND)
            
             # Check if user is authorized to access this data
            if product.owner_user_id != user.id:
                return response(False, "Not authorized to access other user's data", status.HTTP_403_FORBIDDEN)

            if not pwd_context.verify(password, user.password):
                return response(False, "Invalid authorization", status.HTTP_401_UNAUTHORIZED)

            if data.get("sku", product.sku) != product.sku:
                existing_product = db.query(models.Product).filter_by(sku=data['sku']).first()
                if existing_product:
                    return response(False, "Product with this SKU already exists", status.HTTP_400_BAD_REQUEST)

            # Update product data
            product.name = data.get("name", product.name)
            product.description = data.get("description", product.description)
            product.sku = data.get("sku", product.sku)
            product.manufacturer = data.get("manufacturer", product.manufacturer)
            product.quantity = data.get("quantity", product.quantity)

            db.add(product)
            db.commit()
            db.refresh(product)

            return response(True, "Product Updated successfully", status.HTTP_204_NO_CONTENT)

            
        except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)


@app.delete("/v1/product/{product_id}")
async def delete_product(product_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        # Check if product exists
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            return response(False, "Product not found", status.HTTP_404_NOT_FOUND)

        if authorization is None:
            return response(False, "Authorization header missing", status.HTTP_400_BAD_REQUEST)
        try:
            auth_type, encoded_code = authorization.split(" ")
            if auth_type != "Basic":
                return response(False, "Authorization type not supported", status.HTTP_400_BAD_REQUEST)

            code = base64.b64decode(encoded_code).decode("utf-8")
            username, password = code.split(":")

            user = db.query(models.User).filter_by(username=username).first()
            if not user:
                return response(False, "User not found", status.HTTP_404_NOT_FOUND)
            
            # Check if user is authorized to access this data
            if product.owner_user_id != user.id:
                return response(False, "Not authorized to access other user's data", status.HTTP_403_FORBIDDEN)


            if not pwd_context.verify(password, user.password):
                return response(False, "Invalid authorization", status.HTTP_401_UNAUTHORIZED)

            
            # Delete product
            db.delete(product)
            db.commit()

            return response(True, "Product deleted successfully", status.HTTP_204_NO_CONTENT)

        except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
            return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)

@app.get("/v1/product/{product_id}")
async def get_product(product_id: int, db: Session = Depends(get_db)):
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            return response(False, "Product not found", status.HTTP_404_NOT_FOUND)

        return response(True, "Product data retrieved successfully", status.HTTP_200_OK,
                            data=json.loads(json.dumps(product.to_dict(), indent=4, sort_keys=True, default=str)))

AWS_ACCESS_KEY_ID = {"AWS_ACCESS_KEY_ID"}
AWS_SECRET_ACCESS_KEY = {"AWS_SECRET_ACCESS_KEY"}
S3_BUCKET_NAME = {"YOURBUCKETNAME"}

s3 = boto3.client('s3')
#bucket = s3.Bucket(S3_BUCKET_NAME)
uploaded_file_url=f"https://{S3_BUCKET_NAME}.s3.us-east-1.amazonaws.com/"

class CustomJSONEncoder(json.JSONEncoder):
    def default(self, obj):
        if isinstance(obj, datetime):
            return obj.isoformat()
        return super().default(obj)



@app.get("/v1/product/{product_id}/image",response_class=JSONResponse)
def get_images(product_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        # Check authorization header
        if authorization is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization header missing")

        auth_type, encoded_code = authorization.split(" ")
        if auth_type != "Basic":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization type not supported")

        code = base64.b64decode(encoded_code).decode("utf-8")
        username, password = code.split(":")

        # Get user from database
        user = db.query(models.User).filter_by(username=username).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Get product from database
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        # Check if user is owner of the product
        if product.owner_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not authorized to access images for this product")

        # Get images for product from database
        images = db.query(models.Image).filter_by(product_id=product_id).all()

        # Return list of image data
        images_data = [image.to_dict() for image in images]
        return {"data": images_data}
                  

    except Exception as e:
        return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)


    
@app.get("/v1/product/{product_id}/image/{image_id}")
def get_image(product_id: int, image_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        # Check authorization header
        if authorization is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization header missing")

        auth_type, encoded_code = authorization.split(" ")
        if auth_type != "Basic":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization type not supported")

        code = base64.b64decode(encoded_code).decode("utf-8")
        username, password = code.split(":")

        # Get user from database
        user = db.query(models.User).filter_by(username=username).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Get product from database
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        # Check if user is owner of the product
        if product.owner_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not authorized to access images for this product")

        # Get image from database
        image = db.query(models.Image).filter_by(image_id=image_id, product_id=product_id).first()
        if not image:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

        # Return image details
        return response(True, "Image data fetched successfully",
                            status.HTTP_200_OK, data=json.loads(json.dumps(image.to_dict(),
                                                                           indent=4, sort_keys=True, default=str)))
    except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)

@app.post("/v1/product/{product_id}/image")
def create_image(product_id: int, file: UploadFile = File(...), authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        # Check authorization header
        if authorization is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization header missing")

        auth_type, encoded_code = authorization.split(" ")
        if auth_type != "Basic":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization type not supported")

        code = base64.b64decode(encoded_code).decode("utf-8")
        username, password = code.split(":")

        # Get user from database
        user = db.query(models.User).filter_by(username=username).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Get product from database
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        # Check if user is owner of the product
        if product.owner_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not authorized to add images to this product")

        # Check file type
        allowed_file_types = ["jpg", "jpeg", "png"]
        ext = file.filename.split(".")[-1]
        if ext not in allowed_file_types:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=f"Invalid file type. Allowed types: {', '.join(allowed_file_types)}")

        # Generate unique filename
        filename = f"{str(product_id)}_{str(uuid.uuid4())}.{ext}"

        # Upload file to S3 bucket
        s3_client = boto3.client("s3", aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
        s3_client.upload_fileobj(file.file, S3_BUCKET_NAME, filename)

        # Save image details to database
        new_image = models.Image(
            product_id=product_id,
            file_name=filename,
            s3_bucket_path=f"{S3_BUCKET_NAME}/{filename}",
            owner_user_id=user.id
        )

        db.add(new_image)
        db.commit()
        
        return_data = json.loads(
    json.dumps(db.query(models.Image).filter_by(product_id=product_id, file_name=filename).first().to_dict(),
               indent=4, sort_keys=True, default=str))

        return response(True, "Image uploaded Successfully", status.HTTP_201_CREATED, return_data)
    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)


@app.delete("/v1/product/{product_id}/image/{image_id}")
def delete_image(product_id: int, image_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        # Check authorization header
        if authorization is None:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization header missing")

        auth_type, encoded_code = authorization.split(" ")
        if auth_type != "Basic":
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Authorization type not supported")

        code = base64.b64decode(encoded_code).decode("utf-8")
        username, password = code.split(":")

        # Get user from database
        user = db.query(models.User).filter_by(username=username).first()
        if not user:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="User not found")

        # Get image from database
        image = db.query(models.Image).filter_by(image_id=image_id).first()
        if not image:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Image not found")

        # Get product from database
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Product not found")

        # Check if user is owner of the product
        if product.owner_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not authorized to delete images from this product")

        # Check if user is owner of the image
        if image.owner_user_id != user.id:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="User is not authorized to delete this image")

        # Delete image from S3 bucket
        s3_client = boto3.client("s3", aws_access_key_id=AWS_ACCESS_KEY_ID, aws_secret_access_key=AWS_SECRET_ACCESS_KEY)
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=image.file_name)
        

        # Delete image details from database
        db.delete(image)
        db.commit()

        return response(True, "Image deleted successfully", status.HTTP_204_NO_CONTENT)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)
