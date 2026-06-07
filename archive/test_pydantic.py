from pydantic import BaseModel, ValidationError

class Shaft(BaseModel):
    length: float
    diameter: float

try:
    s = Shaft()
except ValidationError as e:
    import json
    print(json.dumps(e.errors(), indent=2))
