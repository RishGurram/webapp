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
from logging.config import dictConfig
import logging
from log import LogConfig
import statsd

c = statsd.StatsClient()

dictConfig(LogConfig().dict())
logger = logging.getLogger("webapp")

models.Base.metadata.create_all(bind=engine)

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

app = FastAPI()

S3_BUCKET_NAME = os.getenv('S3_BUCKET_NAME')
USE_PROFILE = os.getenv('USE_PROFILE', False)

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


@app.post("/v1/rishika")
def create_user(user: User, db: Session = Depends(get_db)):
    try:
        c.incr("Create_User")
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
        return response(True, "User Created Successfully", status.HTTP_201_CREATED, return_data, log_level="info")
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
        c.incr("Get_User")
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
                                                                           indent=4, sort_keys=True, default=str)), log_level="info")
        except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)


@app.put("/v1/user/{user_id}", response_class=JSONResponse)
async def update_user(user_id: int, data: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        c.incr("Update_User")
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

            
            return response(True, "User Updated successfully", status.HTTP_204_NO_CONTENT, log_level="info")

            
        except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)



@app.get("/healthz")
async def health_check():
    c.incr("Health")
    return response(True, "Health check successful", status.HTTP_200_OK, log_level="info")
    



@app.post("/v1/product")
def create_product(product: Product, authorization: str = Header(None),  db: Session = Depends(get_db)):
    try:
        c.incr("Create_Product")

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
        return response(True, "Product Created Successfully", status.HTTP_201_CREATED, return_data, log_level="info")
    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)



@app.put("/v1/product/{product_id}")
async def update_product(product_id: int, data: Product, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        c.incr("Update_Product")
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

            return response(True, "Product Updated successfully", status.HTTP_204_NO_CONTENT, log_level="info")

            
        except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)

@app.patch("/v1/product/{product_id}")
async def update_product(product_id: int, data: dict, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        c.incr("Update_Product")

        
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

            return response(True, "Product Updated successfully", status.HTTP_204_NO_CONTENT, log_level="info")

            
        except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)


@app.delete("/v1/product/{product_id}")
async def delete_product(product_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        c.incr("Delete_Product")
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
            
            # Deleting images related to product
            # Extract the object keys
            # print(db.query(models.Image.s3_bucket_path).filter_by(product_id=product_id).all())
            keys = [obj[0] for obj in db.query(models.Image.s3_bucket_path).filter_by(product_id=product_id).all()]
            # print(keys)

            # Delete the objects in batches of up to 1000
            batches = [keys[i:i+1000] for i in range(0, len(keys), 1000)]

            
            try:
                s3 = boto3.Session(profile_name='dev').client('s3') if USE_PROFILE else boto3.client("s3")
                logger.error("Deleting all images from s3 realted to the image")
                for batch in batches:
                    delete_params = {'Bucket': S3_BUCKET_NAME, 'Delete': {'Objects': [{'Key': obj_key} for obj_key in batch]}}
                    s3.delete_objects(**delete_params)
            except Exception as e:
                logger.error("Couldn't delete Images from S3, deleteing product only : {}".format(str(e)))
            # Delete product
            db.delete(product)
            db.commit()

            return response(True, "Product deleted successfully", status.HTTP_204_NO_CONTENT, log_level="info")

        except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
            return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)

@app.get("/v1/product/{product_id}")
async def get_product(product_id: int, db: Session = Depends(get_db)):
        c.incr("Get_Product")
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            return response(False, "Product not found", status.HTTP_404_NOT_FOUND)

        return response(True, "Product data retrieved successfully", status.HTTP_200_OK,
                            data=json.loads(json.dumps(product.to_dict(), indent=4, sort_keys=True, default=str)), log_level="info")


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
        c.incr("Get_ProductImage")
        
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

        
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            return response(False, "Product not found", status.HTTP_404_NOT_FOUND)

       
        if product.owner_user_id != user.id:
                return response(False, "Not authorized to access other user's data", status.HTTP_403_FORBIDDEN)

        if not pwd_context.verify(password, user.password):
                return response(False, "Invalid authorization", status.HTTP_401_UNAUTHORIZED)
        
        images = db.query(models.Image).filter_by(product_id=product_id).all()

        
        images_data = [image.to_dict() for image in images]
        logger.info("Images fetched successfully 200")
        return {"data": images_data }
        
    
                  

    except Exception as e:
        return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)


    
@app.get("/v1/product/{product_id}/image/{image_id}")
def get_image(product_id: int, image_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        c.incr("Get_ProductImageByID")
        
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

        
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            return response(False, "Product not found", status.HTTP_404_NOT_FOUND)

       
        if product.owner_user_id != user.id:
                return response(False, "Not authorized to access other user's data", status.HTTP_403_FORBIDDEN)

        if not pwd_context.verify(password, user.password):
                return response(False, "Invalid authorization", status.HTTP_401_UNAUTHORIZED)
        
        
        image = db.query(models.Image).filter_by(image_id=image_id, product_id=product_id).first()
        if not image:
            return response(False, "Image not found", status.HTTP_404_NOT_FOUND)

        
        return response(True, "Image data fetched successfully",
                            status.HTTP_200_OK, data=json.loads(json.dumps(image.to_dict(),
                                                                           indent=4, sort_keys=True, default=str)), log_level="info")
    except Exception as e:
            return response(False, "Invalid authorization header : {}".format(str(e)), status.HTTP_400_BAD_REQUEST)

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)

@app.post("/v1/product/{product_id}/image")
def create_image(product_id: int, file: UploadFile = File(...), authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        c.incr("Create_ProductImage")
        
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

       
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            return response(False, "Product not found", status.HTTP_404_NOT_FOUND)
        
        if product.owner_user_id != user.id:
            return response(False, "User is not authorized to upload this image", status.HTTP_401_UNAUTHORIZED)
    
                

        
        if not pwd_context.verify(password, user.password):
                return response(False, "Invalid authorization", status.HTTP_401_UNAUTHORIZED)
        
      
        allowed_file_types = ["jpg", "jpeg", "png"]
        ext = file.filename.split(".")[-1]
        if ext not in allowed_file_types:
            return response(False, f"Invalid file type. Allowed types: {', '.join(allowed_file_types)}" , status.HTTP_400_BAD_REQUEST)

        new_image = models.Image(
            product_id=product_id,
            file_name=file.filename,
            s3_bucket_path=None,
            owner_user_id=user.id
        )

        db.add(new_image)
        db.commit()

        file_key = str(product_id)+"/"+str(new_image.image_id) +"/"+file.filename
      
        s3_client = boto3.Session(profile_name='dev').client("s3") if USE_PROFILE else boto3.client("s3")
        s3_client.put_object(Body=file.file, Bucket=S3_BUCKET_NAME, Key=file_key)

       
        new_image.s3_bucket_path = file_key

        db.add(new_image)
        db.commit()
        
        return_data = json.loads(
    json.dumps(db.query(models.Image).filter_by(image_id=new_image.image_id).first().to_dict(),
               indent=4, sort_keys=True, default=str))

        return response(True, "Image uploaded Successfully", status.HTTP_201_CREATED, return_data, log_level="info")
    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)


@app.delete("/v1/product/{product_id}/image/{image_id}")
def delete_image(product_id: int, image_id: int, authorization: str = Header(None), db: Session = Depends(get_db)):
    try:
        c.incr("Delete_ProductImage")
      
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

       
        image = db.query(models.Image).filter_by(image_id=image_id).first()
        if not image:
           return response(False, "Image not found", status.HTTP_404_NOT_FOUND)

    
        product = db.query(models.Product).filter_by(id=product_id).first()
        if not product:
            return response(False, "Product not found", status.HTTP_404_NOT_FOUND)

    
        if not pwd_context.verify(password, user.password):
                return response(False, "Invalid authorization", status.HTTP_401_UNAUTHORIZED)
      
        if image.owner_user_id != user.id:
            return response(False, "User is not authorized to delete this image", status.HTTP_401_UNAUTHORIZED)

     
        print(S3_BUCKET_NAME, USE_PROFILE)
        s3_client = boto3.Session(profile_name='dev').client("s3") if USE_PROFILE else boto3.client("s3")
        s3_client.delete_object(Bucket=S3_BUCKET_NAME, Key=image.file_name)
        

        db.delete(image)
        db.commit()

        return response(True, "Image deleted successfully", status.HTTP_204_NO_CONTENT, log_level="info")

    except Exception as e:
        return response(False, str(e), status.HTTP_408_REQUEST_TIMEOUT)
