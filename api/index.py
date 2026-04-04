import os
import pickle
import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
# You can remove these if you are letting vercel.json handle the static index.html
# from fastapi.responses import FileResponse 

app = FastAPI()

# 1. FIX CORS: Allow all for development/deployment
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# 2. FIX PATHING: Get the absolute path to the model in the root directory
# Since this file is in /api, we go one level up to find the .pkl
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
model_path = os.path.join(BASE_DIR, "flight_model.pkl")

# Load model once at startup
with open(model_path, "rb") as f:
    data = pickle.load(f)

model        = data["model"]
le_carrier   = data["le_carrier"]
le_origin    = data["le_origin"]
le_dest      = data["le_dest"]
dist_df      = data["distance_lookup"]
feature_cols = data["feature_cols"]

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

@app.get("/api/options") # Added /api prefix to match vercel.json logic
def get_options():
    return {
        "carriers": sorted(le_carrier.classes_.tolist()),
        "origins":  sorted(le_origin.classes_.tolist()),
        "dests":    sorted(le_dest.classes_.tolist()),
    }

@app.get("/api/dests")
def get_dests(origin: str):
    available = dist_df[dist_df["origin"] == origin]["dest"].unique().tolist()
    if not available:
        available = le_dest.classes_.tolist()
    return {"dests": sorted(available)}

@app.post("/api/predict")
def predict(inp: FlightInput):
    dep_delay = (inp.actual_hour * 60 + inp.actual_min) - (inp.sched_hour * 60 + inp.sched_min)
    hour = inp.sched_hour

    route = dist_df[(dist_df["origin"] == inp.origin) & (dist_df["dest"] == inp.dest)]
    distance = float(route["distance"].iloc[0]) if not route.empty else float(dist_df["distance"].mean())

    c_enc = le_carrier.transform([inp.carrier])[0]
    o_enc = le_origin.transform([inp.origin])[0]
    d_enc = le_dest.transform([inp.dest])[0]

    X = pd.DataFrame([[inp.month, inp.day, hour, dep_delay, distance, c_enc, o_enc, d_enc]],
                      columns=feature_cols)
    prob = float(model.predict_proba(X)[0][1])
    return {"probability": prob, "delayed": prob > 0.5}

# NOTE: We removed the @app.get("/") route because your vercel.json 
# handles serving /public/index.html automatically.

if __name__ == "__main__":
    import uvicorn
    # "api.index" matches your folder 'api' and file 'index.py'
    uvicorn.run("api.index:app", host="127.0.0.1", port=8000, reload=True)