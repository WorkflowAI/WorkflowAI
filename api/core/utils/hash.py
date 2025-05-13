import datetime
import hashlib
import json
from typing import Any, Optional

from fastapi.types import IncEx
from pydantic import BaseModel


class _CustomEncoder(json.JSONEncoder):
    """A custom json encoder that defaults to str representation for non-serializable objects."""

    def default(self, o: Any) -> Any:
        if isinstance(o, (datetime.date, datetime.datetime, datetime.time)):
            return o.isoformat()  # Convert dates and datetimes to ISO format strings
        try:
            return json.JSONEncoder.default(self, o)
        except TypeError:
            # Attempt to convert non-JSON-serializable objects to strings
            return str(o)


# TODO: tests
def compute_obj_hash(obj: Any, sort_keys: bool = True) -> str:
    """Compute a hash of an object based on its json representation."""
    obj_str = json.dumps(obj, sort_keys=sort_keys, indent=None, separators=(",", ":"), cls=_CustomEncoder)
    # cannot use python hash function here because it is not
    # stable accross sessions
    return hashlib.md5(obj_str.encode("utf-8")).hexdigest()


def compute_model_hash(
    model: BaseModel,
    exclude: Optional[IncEx] = None,
    exclude_unset: bool = False,
    exclude_defaults: bool = False,
    exclude_none: bool = True,
) -> str:
    dumped = model.model_dump(
        mode="json",
        exclude=exclude,
        exclude_unset=exclude_unset,
        exclude_defaults=exclude_defaults,
        exclude_none=exclude_none,
    )
    # We should use model_dump_json here but sorting keys is not yet possible
    # https://github.com/pydantic/pydantic/issues/7424
    return compute_obj_hash(dumped)


def secure_hash(val: str) -> str:
    return hashlib.sha256(val.encode()).hexdigest()
