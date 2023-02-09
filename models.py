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
    

