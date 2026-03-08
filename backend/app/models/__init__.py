# Import all models here so that Alembic can discover them via Base.metadata
from app.models.product import Product, Tag, product_tags  # noqa: F401
from app.models.price_history import PriceHistory  # noqa: F401
from app.models.watch_config import WatchConfig  # noqa: F401
from app.models.settings import Settings  # noqa: F401
from app.models.domain_rule import DomainRule  # noqa: F401
