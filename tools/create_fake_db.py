import sys
sys.path.append('../app')
from PIL import Image
from app import db, Postcard
from datetime import datetime
from random import uniform
import numpy
import random
import string


def random_coords(times):
    return ((uniform(-180, 180), uniform(-90, 90)) for x in range(times))


def random_string(size=6, chars=string.ascii_uppercase + string.digits):
    return ''.join(random.choice(chars) for _ in range(size))


def random_image(filename):
    a = numpy.random.rand(400, 600, 3) * 255
    img = Image.fromarray(a.astype('uint8')).convert('RGBA')
    img.save('../app/static/postcards/' + filename + '.jpg')


db.create_all()

for coords in random_coords(150):
    card = Postcard(datetime.utcnow(), random_string(), coords[0], coords[1])
    db.session.add(card)
    db.session.commit()
    random_image(str(card.id))
