from sqlalchemy import Column, Integer, String, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime

from database import Base


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    first_name = Column(String, nullable=False)
    last_name = Column(String, nullable=False)
    password = Column(String, nullable=False)
    username = Column(String, nullable=False, unique=True, index=True)
    account_created = Column(DateTime, default=datetime.utcnow)
    account_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    images = relationship("Image", back_populates="owner")


    def to_dict(self):
        return {
            "id": self.id,
            "first_name": self.first_name,
            "last_name": self.last_name,
            "username": self.username,
            "account_created": self.account_created,
            "account_updated": self.account_updated
        }

class Product(Base):
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)
    description = Column(String, nullable=False)
    sku = Column(String, nullable=False, unique=True, index=True)
    manufacturer = Column(String, nullable=False)
    quantity = Column(Integer, nullable=False)
    date_added = Column(DateTime, default=datetime.utcnow)
    date_last_updated = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    owner_user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)

    user = relationship("User", back_populates="products")
    images = relationship("Image", back_populates="product")




    def to_dict(self):
        return {
            
            "id": self.id,
            "name": self.name,
            "description": self.description,
            "sku": self.sku,
            "manufacturer": self.manufacturer,
            "quantity": self.quantity,
            "date_added": self.date_added,
            "date_last_updated": self.date_last_updated,
            "owner_user_id": self.owner_user_id,
        }
User.products = relationship("Product",order_by= "Product.id" , back_populates="user")

class Image(Base):
    __tablename__ = "images"

    image_id = Column(Integer, primary_key=True, index=True)
    product_id = Column(Integer, ForeignKey("products.id"))
    file_name = Column(String, index=True)
    date_created = Column(DateTime, default=datetime.utcnow)
    s3_bucket_path = Column(String, index=True)
    owner_user_id = Column(Integer, ForeignKey("users.id"))

    product = relationship("Product", back_populates="images")
    owner = relationship("User", back_populates="images")

    def to_dict(self):
        return {
            "image_id": self.image_id,
            "product_id": self.product_id,
            "file_name": self.file_name,
            "date_created": self.date_created,
            "s3_bucket_path": self.s3_bucket_path
        }
   

