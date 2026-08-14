import os
import pymongo
import bisect

MONGO_URI = os.getenv(
    "MONGODB_URI", 
    "mongodb+srv://shaileshx006067_db_user:qmTowJMpLK063z7K@cluster0.gdh76cd.mongodb.net/?appName=Cluster0"
)

_ranks = []
_marks = []
_state_rank_airs = []
_state_ranks = []
_loaded = False

def load_data():
    global _ranks, _marks, _state_rank_airs, _state_ranks, _loaded
    if _loaded:
        return
        
    try:
        import certifi
        ca_file = certifi.where()
    except ImportError:
        ca_file = None

    kwargs = {
        "serverSelectionTimeoutMS": 15000,
        "connectTimeoutMS":         15000,
        "socketTimeoutMS":          15000,
    }
    if ca_file:
        kwargs["tls"]       = True
        kwargs["tlsCAFile"] = ca_file
    else:
        kwargs["tls"]                      = True
        kwargs["tlsAllowInvalidCertificates"] = True
        kwargs["tlsAllowInvalidHostnames"]    = True

    try:
        client = pymongo.MongoClient(MONGO_URI, **kwargs)
        
        # Load marks
        col_marks = client["nextstep_neet"]["rank_marks"]
        print("[Predictor] Loading rank-mark data into memory from MongoDB...")
        docs_marks = list(col_marks.find({}, {"_id": 0, "rank": 1, "mark": 1}).sort("rank", 1))
        for d in docs_marks:
            _ranks.append(d["rank"])
            _marks.append(d["mark"])
        print(f"[Predictor] Loaded {len(_ranks)} rank-mark mappings from MongoDB.")
        
        # Load state ranks
        col_sr = client["nextstep_neet"]["state_ranks"]
        print("[Predictor] Loading state-rank data into memory from MongoDB...")
        docs_sr = list(col_sr.find({}, {"_id": 0, "rank": 1, "state_rank": 1}).sort("rank", 1))
        for d in docs_sr:
            _state_rank_airs.append(d["rank"])
            _state_ranks.append(d["state_rank"])
        print(f"[Predictor] Loaded {len(_state_rank_airs)} state-rank mappings from MongoDB.")
            
        _loaded = True
    except Exception as e:
        print(f"[Predictor] Failed to load data: {e}")

def predict_mark(rank: int):
    if not _loaded:
        load_data()
        
    if not _ranks:
        return None
        
    idx = bisect.bisect_left(_ranks, rank)
    if idx < len(_ranks) and _ranks[idx] == rank:
        return _marks[idx]
    if idx == 0:
        return _marks[0]
    if idx == len(_ranks):
        return _marks[-1]
    return _marks[idx - 1]

def predict_state_rank(rank: int):
    if not _loaded:
        load_data()
        
    if not _state_rank_airs:
        return None
        
    idx = bisect.bisect_left(_state_rank_airs, rank)
    if idx < len(_state_rank_airs) and _state_rank_airs[idx] == rank:
        return _state_ranks[idx]
    
    # If the AIR is not exactly found, we could interpolate, 
    # but for state rank it's better to just return the closest or just the lower bound's state rank
    if idx == 0:
        return _state_ranks[0]
    if idx == len(_state_rank_airs):
        return _state_ranks[-1]
        
    # We return the state rank corresponding to the AIR just below it
    return _state_ranks[idx - 1]

