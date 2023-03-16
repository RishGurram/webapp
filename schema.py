from pydantic import BaseModel, EmailStr, Field
from fastapi.exceptions import RequestValidationError
from utils import response
from fastapi import status
from fastapi.responses import JSONResponse

class User(BaseModel):
    first_name: str
    last_name: str
    password: str
    username: EmailStr

    class Config:
        orm_mode = True

class CustomException(Exception):
    def __init__(self, status_code, msg):
        self.status_code = status_code
        self.msg = msg




class LoginSerializer(BaseModel):
    username: str
    password: str

class Product(BaseModel):
    def __init__(self, **data):
        for key, value in data.items():
            if isinstance(value, int) and key != "quantity":
                raise CustomException(status.HTTP_400_BAD_REQUEST, {key: "The value should be string"})
            if key == "quantity" and (isinstance(value, str) or isinstance(value, float)):
                raise CustomException(status.HTTP_400_BAD_REQUEST, {key: "The value should be Integer"})
        super().__init__(**data)
    name: str
    description: str
    sku: str
    manufacturer: str
    quantity: int = Field(ge=0, le=100)

    class Config:
        orm_mode = True

class Image(BaseModel):
    image_id = int
    product_id = int
    file_name = str
    s3_bucket_path = str
   

    class Config:
        orm_mode = True
    
class CustomException(Exception):
    def __init__(self, status_code, msg):
        self.status_code = status_code
        self.msg = msg
        
