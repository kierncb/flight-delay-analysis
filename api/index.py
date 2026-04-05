import os
import pickle
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
import numpy as np

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Path fix
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_path = os.path.join(BASE_DIR, "flight_model.pkl")

with open(model_path, "rb") as f:
    data = pickle.load(f)

# ✅ Logistic Regression params (NOT sklearn model anymore)
coef = np.array(data["coef"])
intercept = data["intercept"]

# classes for encoding (if still needed)
carrier_classes = data["carrier_classes"]
origin_classes  = data["origin_classes"]
dest_classes    = data["dest_classes"]

dist_df = pd.DataFrame(data["distance_lookup"])
feature_cols = data["feature_cols"]


# ---------- helpers ----------
def encode(value, classes):
    try:
        return classes.index(value)
    except ValueError:
        return -1


def sigmoid(z):
    return 1 / (1 + np.exp(-z))


# ---------- schema ----------
class FlightInput(BaseModel):
    origin: str
    dest: str
    carrier: str
    month: int
    day: int
    sched_hour: int
    sched_min: int
    actual_hour: int
    actual_min: int


# ---------- endpoints ----------
@app.get("/options")
def get_options():
    return {
        "carriers": sorted(carrier_classes),
        "origins": sorted(origin_classes),
        "dests": sorted(dest_classes),
    }


@app.get("/dests")
def get_dests(origin: str):
    available = dist_df[dist_df["origin"] == origin]["dest"].unique().tolist()
    if not available:
        available = dest_classes
    return {"dests": sorted(available)}


@app.post("/predict")
def predict(inp: FlightInput):

    dep_delay = (inp.actual_hour * 60 + inp.actual_min) - (inp.sched_hour * 60 + inp.sched_min)
    hour = inp.sched_hour

    route = dist_df[(dist_df["origin"] == inp.origin) & (dist_df["dest"] == inp.dest)]
    distance = float(route["distance"].iloc[0]) if not route.empty else float(dist_df["distance"].mean())

    # encoding (manual safe encoding)
    c_enc = encode(inp.carrier, carrier_classes)
    o_enc = encode(inp.origin, origin_classes)
    d_enc = encode(inp.dest, dest_classes)

    x = np.array([inp.month, inp.day, hour, dep_delay, distance, c_enc, o_enc, d_enc])

    # logistic regression inference
    logit = np.dot(coef, x) + intercept
    prob = sigmoid(logit)

    label = "DELAYED" if prob > 0.5 else "ON-TIME"

    return {
        "prediction": label,
        "probability": float(prob)
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("api.index:app", host="127.0.0.1", port=8000, reload=True)