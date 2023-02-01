from pydantic import BaseModel, EmailStr


class User(BaseModel):
    first_name: str
    last_name: str
    password: str
    email: EmailStr

    class Config:
        orm_mode = True


class LoginSerializer(BaseModel):
    email: str
    password: str
