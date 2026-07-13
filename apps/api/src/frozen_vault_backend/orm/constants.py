"""Shared ORM constants."""

from frozen_vault_backend.orm.enums.base_enums import ProductTypeEnum

# Application policy for best-quality storage at -18 C using the existing broad product types.
FREEZER_STORAGE_DAYS: dict[ProductTypeEnum, int] = {
    ProductTypeEnum.POULTRY: 270,
    ProductTypeEnum.MEAT: 270,
    ProductTypeEnum.FISH: 180,
    ProductTypeEnum.SEAFOOD: 120,
    ProductTypeEnum.VEGETABLE: 60,
    ProductTypeEnum.LIQUID: 120,
    ProductTypeEnum.FRUIT: 90,
    ProductTypeEnum.DESSERT: 120,
    ProductTypeEnum.DAIRY: 90,
}
