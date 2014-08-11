from PIL import Image
from flask import Flask, render_template, flash, redirect, url_for, request
from flask.ext.sqlalchemy import SQLAlchemy
from flask_bootstrap import Bootstrap
from flask_wtf import Form, RecaptchaField
from flask_wtf.file import FileField, FileAllowed, FileRequired
from simplekml import Kml
from urllib.parse import urljoin
from werkzeug.contrib.atom import AtomFeed
from wtforms import TextField, FloatField, SelectField
from wtforms.validators import Required, Optional, NumberRange
import arrow
import geojson
import os

from config import *


app = Flask(__name__)
app.secret_key = SECRET_KEY
app.config['SITENAME'] = SITENAME
app.config['SQLALCHEMY_DATABASE_URI'] = DB_URI
app.config['UPLOAD_FOLDER'] = 'static/postcards'
app.config['RECAPTCHA_PUBLIC_KEY'] = RECAPTCHA_PUBLIC_KEY
app.config['RECAPTCHA_PRIVATE_KEY'] = RECAPTCHA_PRIVATE_KEY
db = SQLAlchemy(app)
Bootstrap(app)


def dm_to_latlng(h, ddd, mmmmm):
    if str.upper(h) == 'S' or str.upper(h) == 'W':
        return '-{ddd}.{mmmmm}'.format(
            ddd=ddd,
            mmmmm=str(round((mmmmm/60), 6))[2:])
    elif str.upper(h) == 'N' or str.upper(h) == 'E':
        return '{ddd}.{mmmmm}'.format(
            ddd=ddd,
            mmmmm=str(round((mmmmm/60), 6))[2:])


class Postcard(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    timestamp = db.Column(db.DateTime)
    name = db.Column(db.String(80))
    lat = db.Column(db.String)
    lng = db.Column(db.String)

    def __init__(self, timestamp, name, lat, lng):
        self.timestamp = timestamp
        self.name = name
        self.lat = lat
        self.lng = lng


class AddPostcardForm(Form):
    name = TextField('', validators=[Required()])
    lat_h = SelectField('', validators=[Required()],
                        choices=[('N', 'N'),
                                 ('S', 'S'),
                                 ('W', 'W'),
                                 ('E', 'E')])
    lat_ddd = FloatField(
        '', validators=[Required(),
                        NumberRange(min=-90, max=90)])
    lat_mmmmm = FloatField('', validators=[Required()])
    lng_h = SelectField('', validators=[Required()],
                        choices=[('N', 'N'),
                                 ('S', 'S'),
                                 ('W', 'W'),
                                 ('E', 'E')])
    lng_ddd = FloatField(
        '', validators=[Required(),
                        NumberRange(min=-180, max=180)])
    lng_mmmmm = FloatField('', validators=[Required()])
    front = FileField(
        '', validators=[FileRequired(),
                        FileAllowed(['jpg'], 'Images only!')])
    back = FileField(
        '', validators=[Optional(),
                        FileAllowed(['jpg'], 'Images only!')])
    recaptcha = RecaptchaField()


def make_external(url):
    return urljoin(request.url_root, url)


def create_feature(point, popupcontent):
    return geojson.Feature(
        geometry=point,
        properties={"popupContent": popupcontent})


def popupcontent(id, name, timestamp, lat, lng):
    if os.path.isfile('static/postcards/%s-back.jpg' % id):
        return '''
            <a href="{3}static/postcards/{0}-front.jpg" class="fancybox"><img src="{3}static/postcards/{0}-front-thumb.jpg" class="img-responsive img-thumbnail"></a>
            <br /><a href="{3}static/postcards/{0}-back.jpg" class="fancybox"><img src="{3}static/postcards/{0}-back-thumb.jpg" class="img-responsive img-thumbnail"></a>
            <br /><small><a href="{3}#14/{1}/{2}">permalink</a> &#124; posted {4}</small>
            '''.format(id, lat, lng, request.url_root, timestamp.humanize())
    else:
        return '''
            <a href="{3}static/postcards/{0}-front.jpg" class="fancybox"><img src="{3}static/postcards/{0}-front-thumb.jpg" class="img-responsive img-thumbnail"></a>
            <br /><small><a href="{3}#14/{1}/{2}">permalink</a> &#124; posted {4}</small>
            '''.format(id, lat, lng, request.url_root, timestamp.humanize())


def get_features():
    postcards = Postcard.query.all()
    postcard_list = []
    for postcard in postcards:
        postcard_list.append(
            create_feature(geojson.Point([float(postcard.lng), float(postcard.lat)]),
                           popupcontent(str(postcard.id),
                                        postcard.name,
                                        arrow.get(postcard.timestamp),
                                        postcard.lat,
                                        postcard.lng)))
    feature_collection = geojson.FeatureCollection(postcard_list)
    return feature_collection


def image_resize(in_filename, out_filename, size=800):
    img = Image.open(in_filename)
    img.thumbnail((size, size), Image.ANTIALIAS)
    img.save(out_filename)


@app.route('/', methods=['GET', 'POST'])
def index():
    geostuff = get_features()
    form = AddPostcardForm()
    form.lat_ddd.data = 31
    form.lat_mmmmm.data = 46.099140
    form.lng_ddd.data = 35
    form.lng_mmmmm.data = 12.822600

    if form.validate_on_submit():
        try:
            lat = dm_to_latlng(form.lat_h.data,
                               form.lat_ddd.data,
                               form.lat_mmmmm.data)
            lng = dm_to_latlng(form.lng_h.data,
                               form.lng_ddd.data,
                               form.lng_mmmmm.data)
            postcard = Postcard(arrow.utcnow().datetime,
                                form.name.data,
                                lat,
                                lng)
            db.session.add(postcard)
            # commit the db entry
            db.session.commit()

            postcard_path = POSTCARDS_FOLDER + '/' + str(postcard.id)

            # save front image
            form.front.data.save(postcard_path + '-front.jpg')
            # resize uploaded image and save it with the same filename
            image_resize(postcard_path + '-front.jpg',
                         postcard_path + '-front.jpg')
            # create thumbnail
            image_resize(postcard_path + '-front.jpg',
                         postcard_path + '-front-thumb.jpg',
                         size=250)

            # save back image if there is one
            form.back.data.save(postcard_path + '-back.jpg')
            if os.path.getsize(postcard_path + '-back.jpg') > 0:
                # resize uploaded image and save it with the same filename
                image_resize(postcard_path + '-back.jpg',
                             postcard_path + '-back.jpg')
                # create thumbnail
                image_resize(postcard_path + '-back.jpg',
                             postcard_path + '-back-thumb.jpg',
                             size=250)
            else:
                # dirty workaround to get rid of the empty file
                os.remove(postcard_path + '-back.jpg')

            flash('Added Postcard', 'success')
            return redirect(url_for('index'))

        except:
            flash('Something went wrong', 'danger')
            return render_template('index.html',
                                   geostuff=geostuff,
                                   form=form,
                                   flash_indicator=True)

    return render_template('index.html', geostuff=geostuff, form=form)


@app.route('/postcards.kml')
def postcards_kml():
    postcards = Postcard.query.all()
    kml = Kml(name='Postcasts')
    for postcard in postcards:
        pnt = kml.newpoint(
            name=postcard.name,
            coords=[(postcard.lng, postcard.lat)])
        if os.path.isfile('static/postcards/%s-back.jpg' % str(postcard.id)):
            pnt.style.balloonstyle.text = '''
                <![CDATA[<table width=100% cellpadding=0 cellspacing=0>
                  <tr>
                    <td>
                      <img width=100% src="{1}static/postcards/{0}-front.jpg"/>
                      <br /><img width=100% src="{1}static/postcards/{0}-back.jpg"/>
                    </td>
                  </tr>
                </table>]]>
                '''.format(str(postcard.id), request.url_root)
        else:
            pnt.style.balloonstyle.text = '''
                <![CDATA[<table width=100% cellpadding=0 cellspacing=0>
                  <tr>
                    <td>
                      <img width=100% src="{1}static/postcards/{0}-front.jpg"/>
                    </td>
                  </tr>
                </table>]]>
                '''.format(str(postcard.id), request.url_root)

    return kml.kml()


@app.route('/postcards.atom')
def postcards_atom():
    feed = AtomFeed(
        SITENAME,
        feed_url=request.url, url=request.url_root)
    postcards = Postcard.query.order_by(Postcard.timestamp.desc()).all()
    for postcard in postcards:
        if os.path.isfile('static/postcards/%s-back.jpg' % str(postcard.id)):
            body = '''
                <img src="{1}static/postcards/{0}-front.jpg">
                <br /><img src="{1}static/postcards/{0}-back.jpg">
                '''.format(str(postcard.id), request.url_root)
        else:
            body = '''
                <img src="{1}static/postcards/{0}-front.jpg">
                '''.format(str(postcard.id), request.url_root)
        feed.add(
            postcard.name,
            body,
            content_type='html',
            author=app.config['SITENAME'],
            url=make_external(
                '#14/{0}/{1}'.format(str(postcard.lat),
                                     str(postcard.lng))),
            updated=postcard.timestamp)

    return feed.get_response()


if __name__ == '__main__':
    app.run(debug=True)
