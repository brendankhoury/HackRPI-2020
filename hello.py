from cloudant import Cloudant
from flask import Flask, render_template, request, jsonify
from flask_cors import CORS
from math import radians, cos, sin, asin, sqrt
import psycopg2 as psyc
import atexit
import os
import json
import requests

geocodeURL = 'https://maps.googleapis.com/maps/api/geocode/json'

app = Flask(__name__, static_url_path='')
CORS(app)
app.config['CORS_HEADERS'] = 'Content-Type'

certs_path = os.getcwd() + "/certs/bouncy-panda-ca.crt"

db_name = 'mydb'
client = None
db = None
geocodekey = None

if 'VCAP_SERVICES' in os.environ:
    vcap = json.loads(os.getenv('VCAP_SERVICES'))
    print('Found VCAP_SERVICES')
    if 'cloudantNoSQLDB' in vcap:
        creds = vcap['cloudantNoSQLDB'][0]['credentials']
        user = creds['username']
        password = creds['password']
        geocodekey = creds['key']
        url = 'https://' + creds['host']
        client = Cloudant(user, password, url=url, connect=True)
        db = client.create_database(db_name, throw_on_exists=False)
elif "CLOUDANT_URL" in os.environ:
    client = Cloudant(os.environ['CLOUDANT_USERNAME'], os.environ['CLOUDANT_PASSWORD'], url=os.environ['CLOUDANT_URL'], connect=True)
    db = client.create_database(db_name, throw_on_exists=False)
elif os.path.isfile('vcap-local.json'):
    with open('vcap-local.json') as f:
        vcap = json.load(f)
        print('Found local VCAP_SERVICES')
        creds = vcap['services']['cloudantNoSQLDB'][0]['credentials']
        user = creds['username']
        password = creds['password']
        geocodekey = creds['key']
        url = 'https://' + creds['host']
        client = Cloudant(user, password, url=url, connect=True)
        db = client.create_database(db_name, throw_on_exists=False)

def db_conn():
  conn = psyc.connect(
    user = "publicuser",
    password = "000000000000",
    host = 'bouncy-panda-64c.gcp-northamerica-northeast1.cockroachlabs.cloud',
    port = 26257,
    database = "cpcoordinator",
    sslmode = "verify-full",
    sslrootcert = certs_path
  )
  return conn

# On IBM Cloud Cloud Foundry, get the port number from the environment variable PORT
# When running this app on the local machine, default the port to 8000
port = int(os.getenv('PORT', 8000))

@app.route('/')
def root():
    return app.send_static_file('index.html')

# /* Endpoint to greet and add a new visitor to database.
# * Send a POST request to localhost:8000/api/visitors with body
# * {
# *     "name": "Bob"
# * }
# */
@app.route('/api/visitors', methods=['GET', 'POST'])
def get_visitor():
    if client:
        return jsonify(list(map(lambda doc: doc['name'], db)))
    else:
        print('No database')
        return jsonify([])


@app.route('/api/signup', methods=['POST'])
def signup():
    requestvals = request.get_json()
    print(requestvals)
    name = requestvals['name']
    email = requestvals['email']
    phone = requestvals['phone']
    password = requestvals['password']
    homeAdd = requestvals['homeAdd']
    workAdd = requestvals['workAdd']
    daysWorked = requestvals['daysWorked']
    startTime = requestvals['startTime']
    endTime = requestvals['endTime']
    ownsCar = requestvals['ownsCar']
    home_lat, home_lon = getLocation(homeAdd)
    work_lat, work_lon = getLocation(workAdd)
    db_connection = db_conn()
    with db_connection.cursor() as cur:
        cur.execute(
        f"INSERT INTO users (email, name, password, homeAdd, workAdd, daysWorked, startTime, endTime, ownsCar, home_lat, home_lon, work_lat, work_lon) \
          VALUES ('{email}', '{name}', '{password}', '{homeAdd}', '{workAdd}', 'mwf', '{startTime}', '{endTime}', {ownsCar}, {home_lat}, {home_lon}, {work_lat}, {work_lon})"
        )
    db_connection.close()
    return "200"

@app.route('/api/signin', methods=['GET', 'POST'])
def signin():
    db_connection = db_conn()
    user_email = request.values['email']
    print(user_email)
    user_password = request.values['password']
    with db_connection.cursor() as cur:
        cur.execute(f"SELECT password FROM Users WHERE email = '{user_email}'")
        password = cur.fetchone()
        if (password == user_password):
            return "true"
        else:
            return ""
    db_connection.close()


@app.route('/api/getclose', methods=['POST'])
def getclose():
    db_connection = db_conn()
    user_email = request.values.get('email')
    with db_connection.cursor() as cur:
        cur.execute(f"SELECT * FROM users WHERE email = '{user_email}'")
        curUser = cur.fetchone()
        print(curUser)
        cur.execute(f"SELECT (name, email) FROM users ORDER BY SQRT( POW({curUser['home_lat']} - home_lat, 2) + POW({curUser['home_lon']} - home_lon, 2) )")
        closestUsers = cur.fetchAll()
        print(closestUsers)




# /**
#  * Endpoint to get a JSON array of all the visitors in the database
#  * REST API example:
#  * <code>
#  * GET http://localhost:8000/api/visitors
#  * </code>
#  *
#  * Response:
#  * [ "Bob", "Jane" ]
#  * @return An array of all the visitor names
#  */
@app.route('/api/visitors', methods=['POST'])
def put_visitor():
    user = request.json['name']
    data = {'name':user}
    if client:
        my_document = db.create_document(data)
        data['_id'] = my_document['_id']
        return jsonify(data)
    else:
        print('No database')
        return jsonify(data)

@atexit.register
def shutdown():
    if client:
        client.disconnect()

def distanceBetween(address1, address2):
    loc1 = getLocation(address1)
    loc2 = getLocation(address2)
    return haversine(loc1[0], loc1[1], loc2[0], loc2[1])


def getLocation(address):
    endpoint = f"{geocodeURL}?address={address}&key={geocodekey}"
    r = requests.get(endpoint)
    try:
        results = r.json()['results']
        location = results[0]['geometry']['location']
        return [location['lat'], location['lng']]
    except:
        pass


def haversine(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(radians, [lon1, lat1, lon2, lat2])

    # haversine formula
    dlon = lon2 - lon1
    dlat = lat2 - lat1
    a = sin(dlat/2)**2 + cos(lat1) * cos(lat2) * sin(dlon/2)**2
    c = 2 * asin(sqrt(a))
    r = 3956
    return c * r

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=port, debug=True)
    print(certs_path)
    db_conn()
