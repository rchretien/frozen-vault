"""Enumeration classes for the ORM models, Pydantic schemas and CRUD classes."""

from enum import Enum


# Enumerations for Pydantic models
class ProductTypeEnum(str, Enum):
    """Enumeration for product types."""

    POULTRY = "poultry 🍗"
    MEAT = "meat 🥩"
    FISH = "fish 🐟"
    SEAFOOD = "seafood 🍱"
    VEGETABLE = "vegetable 🥦"
    LIQUID = "liquid 💧"
    FRUIT = "fruit 🍓"
    DESSERT = "dessert 🍨"
    DAIRY = "dairy 🥛"


class ProductLocationEnum(str, Enum):
    """Enumeration for product locations."""

    REFRIGERATOR = "refrigerator"
    BIG_FREEZER = "big freezer"
    SMALL_FREEZER = "small freezer"


class ProductUnitEnum(str, Enum):
    """Enumeration for product units."""

    GRAM = "g"
    BOXES = "boxes"
    BOTTLES = "bottles"


# Enumerations for allowed order_by options
class OrderByEnum(str, Enum):
    """Enumeration for ordering options."""

    ID = "id"
    NAME = "name"
    CREATION_DATE = "creation_date"
    EXPIRY_DATE = "expiry_date"
