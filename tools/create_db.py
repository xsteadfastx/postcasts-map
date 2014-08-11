import sys
sys.path.append('../app')
from app import db


db.create_all()
