#Import the required libraries
import psycopg2
from psycopg2.extras import RealDictCursor
import json
import os

def set_up_connection():
	try:
		# If the requested key does not exist, it raises `KeyError(key)`.
		host = os.environ['HOST']
		username = os.environ['USERNAME']
		password = os.environ['PASSWORD']
		database = os.environ['DATABASE']
	except KeyError:
		print('Please define the environment variable HOST, USERNAME, PASSWORD, DATABASE')
		# These are the test variables
		# We set them using
		# export HOST="matterdashboarddb.***********.eu-west-1.rds.amazonaws.com"
		# export USERNAME="postgres"
		# export PASSWORD="******"
		# export DATABASE="matterdashboard_dev"

	#Create the postgres connection
	global conn
	conn = psycopg2.connect(
		host=host,
		database=database,
		user=username,
		password=password
	)
	return conn

def lambda_handler_thing_deleted(event, context):
	print("lambda_handler_thing_deleted")
	print(json.dumps(event))
	#Create the postgres connection
	global conn
	conn = set_up_connection()

	#print(json.dumps(event))
	for record in event['Records']:
			try:
					message = json.dumps(record['Sns']['Message'])
					#print(f"Processing message {message}")
					jsonMessage = json.loads(record['Sns']['Message'])
					thingName = jsonMessage['thing_name']
					shadowName = jsonMessage['shadow_name']
					nodeId = shadowName.split('_')[0]
					endpointId = shadowName.split('_')[1]

					deleteFromDb(thingName, nodeId)
			except Exception as err:
					print("An error occurred")
					print(err)
					conn.close()

					# TODO implement
					return {
							'statusCode': 500,
							'body': json.dumps('ERROR')
					}
					raise err

	conn.close()

	# TODO implement
	return {
			'statusCode': 200,
			'body': json.dumps('OK')
	}

def lambda_handler_thing_updated(event, context):
	print("lambda_handler_thing_updated")
	print(json.dumps(event))
	#Create the postgres connection
	global conn
	conn = set_up_connection()

	#print(json.dumps(event))
	for record in event['Records']:
			try:
					message = json.dumps(record['Sns']['Message'])
					#print(f"Processing message {message}")
					jsonMessage = json.loads(record['Sns']['Message'])
					thingName = jsonMessage['thing_name']
					shadowName = jsonMessage['shadow_name']

					if (shadowName.includes("events")):
						nodeId = shadowName.split('_')[1]
						continue #lets leave here for now as we dont handle events updates in the lambda yet
					else:
						nodeId = shadowName.split('_')[0]
						endpointId = shadowName.split('_')[1]

						# Iterate through the object
						attributes = jsonMessage['reported']
						jsonEndpoints = attributes_to_json(attributes)
						#print(f"Processing message {jsonEndpoints}")
						controllerId = findControllerId(thingName)
						cacheToDb(controllerId, nodeId, jsonEndpoints)
			except Exception as err:
					print("An error occurred")
					print(err)
					conn.close()

					# TODO implement
					return {
							'statusCode': 500,
							'body': json.dumps('ERROR')
					}
					raise err

	conn.close()

	# TODO implement
	return {
			'statusCode': 200,
			'body': json.dumps('OK')
	}

def findControllerId(thing_name):
	cur = conn.cursor(cursor_factory = RealDictCursor)
	val = (thing_name,)
	sql = "select id from \"Controller\" where \"name\"=%s"
	cur.execute(sql,val)
	result = cur.fetchone() #check the result
	return result['id']

def cacheToDb(controllerId, id, endpoints):
	cur = conn.cursor(cursor_factory = RealDictCursor)

	print("Trying to find Node Id: %s and updating its timestamp: " % id)

	val = (id, controllerId)
	#we will adjust the historyBitmap
	# 1) first we work out what is the next most significant bit after this number
    #    - Math.pow(2,Math.ceil(Math.log(historyBitmap+1)/Math.log(2))) //e.g. 5 = 101 so next bit is 8 since we want 1000
    # 2) then we make an adjustment for the number of days since the last update
    #    - Math.pow(2,daysSinceUpdate-1)  // e.g. if its been 2 days since the last update adjustment = 2^1 = 2
	# 3) then we multiply the nextBit by the adjustment and add this to the currentBitmap
    #	- nextBit*adjustment+currentBitmap // e.g. we multiply 8 by 2 to get 16 and add the current bitmap of 5 so we get 21 or 10101
	# 4) Finally, we need to stop this getting too big so divide by 2 after going over 30 days
				
	sql = "UPDATE \"Node\" SET \"historyBitmap\" = power(2,ceil(log(\"historyBitmap\"+1)/log(2)))*pow(2,(DATE(now()) - DATE(\"createdAt\"))-1)+\"historyBitmap\" WHERE (DATE(now())  - DATE(\"createdAt\")) > 0 and \"name\"=%s and \"controllerId\"=%s"
	print(sql % val)
	cur.execute(sql,val)
	conn.commit()

	sql = "UPDATE \"Node\" SET \"historyBitmap\" = floor(\"historyBitmap\"/2) WHERE \"historyBitmap\" > power(2,31) and \"name\"=%s and \"controllerId\"=%s"
	print(sql % val)
	cur.execute(sql,val)
	conn.commit()
	#we will adjust the historyBitmap

	#we will adjust the datestamp
	sql = "UPDATE \"Node\" SET \"createdAt\"='now()' WHERE \"name\"=%s and \"controllerId\"=%s RETURNING id"
	print(sql % val)
	cur.execute(sql,val)
	result = cur.fetchone() #check the result
	if (result is None):
		# We dont already have a Node - now create one
		print("Inserting Node: %s for controllerId: %s " % (id, controllerId))
		val = (id, id, controllerId)
		sql = "INSERT into \"Node\" (\"name\", body, \"controllerId\", \"historyBitmap\") VALUES(%s,%s,%s,1) RETURNING id"
		cur.execute(sql,val)
		id = cur.fetchone()["id"]
		#print(id)
	else:
		id = result["id"]

		#print(id)

	conn.commit()

	for endpoint in endpoints:
		# update the endpoints
		endpointId = int(endpoint)
		inputData = {
			"name": endpoint,
			"body": json.dumps(endpoints[endpoint]),
			"nodeId": int(id)
		}
		tempresp = None
		tempEndpoint = None

		print("Trying to find Endpoint: %s for nodeId: %s and updating its timestamp: " % (endpoint, id))
		val = (inputData['body'], endpoint,id)
		sql = "UPDATE \"Endpoint\" SET \"createdAt\"='now()' , body= %s WHERE \"name\"=%s and \"nodeId\"=%s RETURNING id"
		cur.execute(sql,val)
		result = cur.fetchone() #check the result
		if (result is None):
			# We dont already have an Endpoint - now create one
			print("Inserting Endpoint: %s for nodeId: %s " % (inputData['name'], inputData['nodeId']))
			val = (inputData['name'], inputData['body'], inputData['nodeId'])
			sql = "INSERT into \"Endpoint\" (\"name\", body, \"nodeId\") VALUES(%s,%s,%s) RETURNING id"
			cur.execute(sql,val)
			endpointId = cur.fetchone()["id"]
			#print(endpointId)
		else:
			endpointId = result["id"]
			#print(endpointId)

		conn.commit()

		# Now we will add/update the clusters
		clusters = endpoints[endpoint]
		for cluster in clusters:
			# update the clusters
			clusterId = int(cluster)
			clusterInputData = {
				"name": cluster,
				"body": json.dumps(clusters[cluster]),
				"clusterDefnCode": clusterId,
				"endpointId": endpointId
			}

			print("Trying to find Cluster: %s for endpointId: %s and updating its timestamp: " % (cluster, endpointId))
			#print(clusterInputData)
			val = (clusterInputData['body'],cluster,endpointId)
			sql = "UPDATE \"Cluster\" SET \"createdAt\"='now()' , body= %s WHERE \"name\"=%s and \"endpointId\"=%s RETURNING id"
			print(sql % val)
			cur.execute(sql,val)
			result = cur.fetchone() #check the result
			if (result is None):
				print("We dont already have an Cluster - now create one")
				print("Inserting Cluster: %s for endpointId: %s " % (clusterInputData['name'], clusterInputData['endpointId']))
				# We dont already have an Cluster - now create one
				try:
					val = (clusterInputData['name'], clusterInputData['body'], clusterInputData['clusterDefnCode'], clusterInputData['endpointId'])
					sql = "INSERT into \"Cluster\" (\"name\", body, \"clusterDefnCode\", \"endpointId\") VALUES(%s,%s,%s,%s) RETURNING id"
					cur.execute(sql,val)
					clusterId = cur.fetchone()["id"]
					#print(clusterId)
				except Exception as error:
					print(error)
					if conn is not None:
						conn.rollback() # We got here because there isnt a matching AttributeDefn
					continue
			else:
				clusterId = result["id"]
				#print(clusterId)

			conn.commit()

			# Now add/update the attributes
			clusterCode = int(cluster)
			attributes = clusters[cluster]
			for attribute in attributes:
				# update the attributes
				attributeId = int(attribute)
				attributeInputData = {
					"name": attribute,
					"body": json.dumps(attributes[attribute]),
					"attributeDefnCode": attributeId,
					"clusterDefnCode": clusterCode,
					"clusterId": clusterId
				}

				print("Trying to find Attribute: %s for clusterId: %s and updating its timestamp: " % (attribute, clusterId))
				#print(attributeInputData)
				val = (attributeInputData['body'],attribute,clusterId)
				sql = "UPDATE \"Attribute\" SET \"createdAt\"='now()' , body= %s WHERE \"name\"=%s and \"clusterId\"=%s RETURNING id"
				print(sql % val)
				cur.execute(sql,val)
				result = cur.fetchone() #check the result
				if (result is None):
					print("We dont already have an Attribute - now create one")

					# We dont already have an Attribute - now create one
					try:
						print("Inserting Attribute: %s for clusterId: %s " % (attributeInputData['name'], attributeInputData['clusterId']))
						val = (attributeInputData['name'], attributeInputData['body'], attributeInputData['attributeDefnCode'], attributeInputData['clusterDefnCode'], attributeInputData['clusterId'])
						sql = "INSERT into \"Attribute\" (\"name\", body, \"attributeDefnCode\", \"clusterDefnCode\", \"clusterId\") VALUES(%s,%s,%s,%s,%s) RETURNING id"
						#print(sql % val)
						cur.execute(sql,val)
						attributeId = cur.fetchone()["id"]
						#print(attributeId)
					except Exception as error:
						print(error)
						print(sql % val)
						if conn is not None:
							conn.rollback() # We got here because there isnt a matching AttributeDefn
						continue
				else:
					attributeId = result["id"]
					#print(attributeId)

		conn.commit()
		cur.close()
		return

def attributes_to_json(attributes):
    data_dict = {}
    attribute_dict = {}
    cluster_dict = {}
    for attribute in attributes:
        # go thru each attribute and build a json object
        if attribute in attributes:
            attribute_array = attribute.split('/')
            endpoint_key = attribute_array[0]
            cluster_key = attribute_array[1]
            attribute_key = attribute_array[2]
            if cluster_key not in cluster_dict:
                # if we havent seen that cluster before initialize the attribute dictionaries
                attribute_dict = {}
            if endpoint_key not in data_dict:
                # if we havent seen that endpoint before initialize the cluster dictionaries
                cluster_dict = {}
            attribute_dict[attribute_key] = attributes[attribute]
            cluster_dict[cluster_key] = attribute_dict
            data_dict[endpoint_key] = cluster_dict
    return data_dict

def deleteFromDb(controllerName, id):
	cur = conn.cursor(cursor_factory = RealDictCursor)

	print("Trying to delete all attributes for Node Id: %s : " % id)
	val = (id, controllerName)
	sql = "delete from \"Attribute\" where id in (select a.id FROM \"Attribute\" a JOIN \"Cluster\" c ON a.\"clusterId\"  = c.id JOIN \"Endpoint\" e ON c.\"endpointId\"  = e.id JOIN \"Node\" n ON e.\"nodeId\" = n.id INNER JOIN \"Controller\" co ON n.\"controllerId\" = co.id WHERE n.\"name\" = %s AND co.name = %s)"
	cur.execute(sql,val)

	conn.commit()

	print("Trying to delete all clusters for Node Id: %s : " % id)
	val = (id, controllerName)
	sql = "delete from \"Cluster\" where id in (SELECT c.id FROM \"Cluster\" c INNER JOIN \"Endpoint\" e ON c.\"endpointId\"  = e.id INNER JOIN \"Node\" n ON e.\"nodeId\" = n.id INNER JOIN \"Controller\" co ON n.\"controllerId\" = co.id WHERE n.\"name\" = %s AND co.name = %s)"
	cur.execute(sql,val)

	conn.commit()

	print("Trying to delete all endpoints for Node Id: %s : " % id)
	val = (id, controllerName)
	sql = "delete from \"Endpoint\" where id in (SELECT e.id FROM \"Endpoint\" e INNER JOIN \"Node\" n ON e.\"nodeId\" = n.id INNER JOIN \"Controller\" co ON n.\"controllerId\" = co.id WHERE n.\"name\" = %s AND co.name = %s)"
	cur.execute(sql,val)

	conn.commit()

	print("Trying to delete all events for Node Id: %s : " % id)
	val = (id, controllerName)
	sql = "delete from \"Event\" where id in (SELECT e.id FROM \"Event\" e INNER JOIN \"Node\" n ON e.\"nodeId\" = n.id INNER JOIN \"Controller\" co ON n.\"controllerId\" = co.id WHERE n.\"name\" = %s AND co.name = %s)"
	cur.execute(sql,val)

	conn.commit()

	print("Trying to delete Node Id: %s : " % id)
	val = (id, controllerName)
	sql = "delete from \"Node\" where id in (SELECT n.id FROM \"Node\" n INNER JOIN \"Controller\" co ON n.\"controllerId\" = co.id WHERE n.\"name\" = %s AND co.name = %s)"
	cur.execute(sql,val)

	conn.commit()


def main_lambda_handler():


	#Create the postgres connection
	global conn
	conn = set_up_connection()

	controllerId = findControllerId("mcc-thing-ver01-1")

	myAttributesStr = "{\"0/53/39\":0,\"0/53/31\":0,\"0/53/29\":0,\"0/53/6\":0,\"0/53/27\":0,\"0/53/46\":0,\"0/53/43\":0,\"0/53/40\":0,\"0/53/14\":0,\"0/53/65528\":[],\"0/53/28\":0,\"0/53/30\":0,\"0/53/22\":0,\"0/53/48\":0,\"0/53/26\":0,\"0/53/47\":0,\"0/53/20\":0,\"0/53/15\":0,\"0/53/7\":[],\"0/53/36\":0,\"0/53/54\":0,\"0/53/41\":0,\"0/53/18\":0,\"0/53/55\":0,\"0/53/53\":0,\"0/53/52\":0,\"0/53/49\":0,\"0/53/32\":0,\"0/53/33\":0,\"0/53/65533\":1,\"0/53/17\":0,\"0/53/44\":0,\"0/53/65532\":15,\"0/53/35\":0,\"0/53/38\":0,\"0/53/65529\":[0],\"0/53/62\":[],\"0/53/21\":0,\"0/53/50\":0,\"0/53/19\":0,\"0/53/42\":0,\"0/53/23\":0,\"0/53/37\":0,\"0/53/45\":0,\"0/53/8\":[],\"0/53/24\":0,\"0/53/16\":0,\"0/53/51\":0,\"0/53/34\":0,\"0/53/65531\":[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31,32,33,34,35,36,37,38,39,40,41,42,43,44,45,46,47,48,49,50,51,52,53,54,55,56,57,58,59,60,61,62,65528,65529,65531,65532,65533],\"0/53/25\":0,\"0/30/0\":[],\"0/30/65532\":0,\"0/30/65529\":[],\"0/30/65531\":[0,65528,65529,65531,65532,65533],\"0/30/65533\":1,\"0/30/65528\":[],\"0/54/3\":6,\"0/54/8\":0,\"0/54/65528\":[],\"0/54/12\":0,\"0/54/65531\":[0,1,2,3,4,5,6,7,8,9,10,11,12,65528,65529,65531,65532,65533],\"0/54/65532\":3,\"0/54/2\":3,\"0/54/0\":\"FC0n3jib\",\"0/54/65533\":1,\"0/54/10\":80863,\"0/54/7\":0,\"0/54/65529\":[0],\"0/54/9\":127584,\"0/50/65531\":[65528,65529,65531,65532,65533],\"0/50/65528\":[1],\"0/50/65532\":0,\"0/50/65529\":[0],\"0/50/65533\":1,\"0/55/65529\":[0],\"0/55/6\":0,\"0/55/3\":0,\"0/55/1\":false,\"0/55/8\":496,\"0/55/65533\":1,\"0/55/2\":0,\"0/55/65531\":[0,1,2,3,4,5,6,7,8,65528,65529,65531,65532,65533],\"0/55/65532\":3,\"0/55/4\":0,\"0/55/65528\":[],\"0/55/5\":0,\"0/31/0\":[{\"privilege\":5,\"authMode\":2,\"subjects\":[112233],\"targets\":null,\"fabricIndex\":1}],\"0/31/1\":[],\"0/31/65529\":[],\"0/31/65532\":0,\"0/31/65533\":1,\"0/31/4\":4,\"0/31/3\":3,\"0/31/2\":4,\"0/31/65528\":[],\"0/31/65531\":[0,1,2,3,4,65528,65529,65531,65532,65533],\"0/64/65531\":[0,65528,65529,65531,65532,65533],\"0/64/0\":[{\"label\":\"room\",\"value\":\"bedroom 2\"},{\"label\":\"orientation\",\"value\":\"North\"},{\"label\":\"floor\",\"value\":\"2\"},{\"label\":\"direction\",\"value\":\"up\"}],\"0/64/65528\":[],\"0/64/65533\":1,\"0/64/65532\":0,\"0/64/65529\":[],\"0/52/65533\":1,\"0/52/65531\":[0,1,2,3,65528,65529,65531,65532,65533],\"0/52/1\":347328,\"0/52/65529\":[0],\"0/52/0\":[{\"id\":14029,\"name\":\"14029\",\"stackFreeCurrent\":null,\"stackFreeMinimum\":null,\"stackSize\":null},{\"id\":14028,\"name\":\"14028\",\"stackFreeCurrent\":null,\"stackFreeMinimum\":null,\"stackSize\":null},{\"id\":14027,\"name\":\"14027\",\"stackFreeCurrent\":null,\"stackFreeMinimum\":null,\"stackSize\":null},{\"id\":14026,\"name\":\"14026\",\"stackFreeCurrent\":null,\"stackFreeMinimum\":null,\"stackSize\":null},{\"id\":14025,\"name\":\"14025\",\"stackFreeCurrent\":null,\"stackFreeMinimum\":null,\"stackSize\":null}],\"0/52/2\":1307456,\"0/52/65528\":[],\"0/52/3\":1307456,\"0/52/65532\":1,\"0/29/65533\":1,\"0/29/65531\":[0,1,2,3,65528,65529,65531,65532,65533],\"0/29/3\":[1,2],\"0/29/1\":[3,4,29,30,31,40,42,43,44,45,47,48,49,50,51,52,53,54,55,56,60,62,63,64,65,70,1029,4294048774],\"0/29/2\":[41],\"0/29/0\":[{\"deviceType\":22,\"revision\":1}],\"0/29/65532\":0,\"0/29/65529\":[],\"0/29/65528\":[],\"0/40/19\":{\"caseSessionsPerFabric\":3,\"subscriptionsPerFabric\":65535},\"0/40/14\":\"\",\"0/40/2\":65521,\"0/40/16\":false,\"0/40/6\":\"XX\",\"0/40/15\":\"TEST_SN\",\"0/40/3\":\"TEST_PRODUCT1\",\"0/40/65531\":[0,1,2,3,4,5,6,7,8,9,10,11,12,13,14,15,16,18,19,20,65528,65529,65531,65532,65533],\"0/40/9\":1,\"0/40/10\":\"1.0\",\"0/40/11\":\"20200101\",\"0/40/12\":\"\",\"0/40/1\":\"TEST_VENDOR\",\"0/40/18\":\"AD262C8EA2EC4CDA\",\"0/40/7\":0,\"0/40/65532\":0,\"0/40/65533\":2,\"0/40/8\":\"TEST_VERSION\",\"0/40/13\":\"\",\"0/40/65528\":[],\"0/40/4\":32769,\"0/40/0\":1,\"0/40/65529\":[],\"0/40/20\":{\"finish\":2,\"primaryColor\":5},\"0/40/5\":\"\",\"0/63/3\":3,\"0/63/65531\":[0,1,2,3,65528,65529,65531,65532,65533],\"0/63/1\":[],\"0/63/2\":12,\"0/63/65528\":[2,5],\"0/63/0\":[],\"0/63/65532\":0,\"0/63/65529\":[0,1,3,4],\"0/63/65533\":2,\"0/47/0\":0,\"0/47/65528\":[],\"0/47/1\":3,\"0/47/65533\":2,\"0/47/31\":[],\"0/47/16\":0,\"0/47/65529\":[],\"0/47/65532\":2,\"0/47/15\":false,\"0/47/14\":0,\"0/47/2\":\"B1\",\"0/47/65531\":[0,1,2,14,15,16,31,65528,65529,65531,65532,65533],\"0/43/1\":[\"en-US\",\"de-DE\",\"fr-FR\",\"en-GB\",\"es-ES\",\"zh-CN\",\"it-IT\",\"ja-JP\"],\"0/43/65533\":1,\"0/43/65528\":[],\"0/43/65529\":[],\"0/43/0\":\"en-US\",\"0/43/65532\":0,\"0/43/65531\":[0,1,65528,65529,65531,65532,65533],\"0/60/65529\":[0,1,2],\"0/60/65533\":1,\"0/60/65528\":[],\"0/60/0\":0,\"0/60/65532\":0,\"0/60/65531\":[0,1,2,65528,65529,65531,65532,65533],\"0/48/3\":2,\"0/48/65528\":[1,3,5],\"0/48/2\":0,\"0/48/65531\":[0,1,2,3,4,65528,65529,65531,65532,65533],\"0/48/1\":{\"failSafeExpiryLengthSeconds\":60,\"maxCumulativeFailsafeSeconds\":900},\"0/48/0\":0,\"0/48/65532\":0,\"0/48/4\":true,\"0/48/65533\":1,\"0/48/65529\":[0,2,4],\"0/65/65531\":[0,65528,65529,65531,65532,65533],\"0/65/65532\":0,\"0/65/65533\":1,\"0/65/0\":[],\"0/65/65528\":[],\"0/65/65529\":[],\"0/70/5\":2,\"0/70/65532\":1,\"0/70/65528\":[1],\"0/70/3\":[],\"0/70/1\":300,\"0/70/65531\":[0,1,2,3,4,5,65528,65529,65531,65532,65533],\"0/70/65529\":[0,2,3],\"0/70/2\":300,\"0/70/4\":0,\"0/70/0\":2000,\"0/70/65533\":1,\"0/3/65528\":[],\"0/3/0\":0,\"0/3/65533\":4,\"0/3/1\":2,\"0/3/65529\":[0,64],\"0/3/65531\":[0,1,65528,65529,65531,65532,65533],\"0/3/65532\":0,\"0/4/65529\":[0,1,2,3,4,5],\"0/4/65532\":1,\"0/4/0\":128,\"0/4/65531\":[0,65528,65529,65531,65532,65533],\"0/4/65533\":4,\"0/4/65528\":[0,1,2,3],\"0/45/65528\":[],\"0/45/65532\":1,\"0/45/65531\":[0,65528,65529,65531,65532,65533],\"0/45/65533\":1,\"0/45/0\":0,\"0/45/65529\":[],\"0/42/2\":0,\"0/42/0\":[],\"0/42/1\":true,\"0/42/65533\":1,\"0/42/65532\":0,\"0/42/65528\":[],\"0/42/3\":0,\"0/42/65529\":[0],\"0/42/65531\":[0,1,2,3,65528,65529,65531,65532,65533],\"0/44/65532\":0,\"0/44/65533\":1,\"0/44/0\":0,\"0/44/2\":[0,1,2,3,4,5,6,8,9,10,11,7],\"0/44/65529\":[],\"0/44/65531\":[0,1,2,65528,65529,65531,65532,65533],\"0/44/1\":0,\"0/44/65528\":[],\"0/51/8\":false,\"0/51/7\":[],\"0/51/5\":[],\"0/51/2\":495,\"0/51/65532\":0,\"0/51/0\":[{\"name\":\"docker0\",\"isOperational\":false,\"offPremiseServicesReachableIPv4\":null,\"offPremiseServicesReachableIPv6\":null,\"hardwareAddress\":\"AkJiJRWL\",\"IPv4Addresses\":[\"rBEAAQ==\"],\"IPv6Addresses\":[\"\"],\"type\":0},{\"name\":\"wlo1\",\"isOperational\":true,\"offPremiseServicesReachableIPv4\":null,\"offPremiseServicesReachableIPv6\":null,\"hardwareAddress\":\"FC0n3jib\",\"IPv4Addresses\":[\"wKgBDg==\"],\"IPv6Addresses\":[\"IAELtka1bADgnydWNt+hcw==\",\"IAELtka1bAAfgAYVpJAz/Q==\",\"/oAAAAAAAAA3jDKMnK3aXQ==\"],\"type\":1},{\"name\":\"eno1\",\"isOperational\":false,\"offPremiseServicesReachableIPv4\":null,\"offPremiseServicesReachableIPv6\":null,\"hardwareAddress\":\"bMIXcWy3\",\"IPv4Addresses\":[],\"IPv6Addresses\":[],\"type\":2},{\"name\":\"lo\",\"isOperational\":true,\"offPremiseServicesReachableIPv4\":null,\"offPremiseServicesReachableIPv6\":null,\"hardwareAddress\":\"AAAAAAAA\",\"IPv4Addresses\":[\"fwAAAQ==\"],\"IPv6Addresses\":[\"AAAAAAAAAAAAAAAAAAAAAQ==\"],\"type\":0}],\"0/51/4\":0,\"0/51/3\":0,\"0/51/65529\":[0],\"0/51/1\":1,\"0/51/65528\":[],\"0/51/65531\":[0,1,2,3,4,5,6,7,8,65528,65529,65531,65532,65533],\"0/51/65533\":1,\"0/51/6\":[],\"0/1029/1\":0,\"0/1029/65529\":[],\"0/1029/65532\":0,\"0/1029/65528\":[],\"0/1029/65531\":[0,1,2,65528,65529,65531,65532,65533],\"0/1029/2\":10000,\"0/1029/0\":0,\"0/1029/65533\":3,\"0/62/65528\":[1,3,5,8],\"0/62/0\":[{\"noc\":\"FTABAQEkAgE3AyQTAhgmBIAigScmBYAlTTo3BiQVASQRAhgkBwEkCAEwCUEEq2rQlyu355YVuzYgIwLKsRHFjVFjlEVZekIvdwdb4vRCdp6KrZ5b1ehV/hs1sivfYmE+z+4rdXU/ObsWQ1mxPTcKNQEoARgkAgE2AwQCBAEYMAQUF9mpI+42emfqOrGMcxZjs+Ilf+owBRRUN36wfbtRWZ3r9qlC5P/KMyKK2xgwC0DtQx+1QM6zUAQAZSw3HzQd26LjCLA5eZkaDHFM8qMV12JR8HtF1XcZtsSJ+/K0AleNhc+OSzY1468RD+ae+HriGA==\",\"icac\":\"FTABAQEkAgE3AyQUARgmBIAigScmBYAlTTo3BiQTAhgkBwEkCAEwCUEEg/hndnKb3IsxN51Y7LjJxLQ4fTSmzqBMThex9bLPK9dX0YjBZSMvu+Eq3eziKVWkBDheFHqM/0IL+q4eRK0AvzcKNQEpARgkAmAwBBRUN36wfbtRWZ3r9qlC5P/KMyKK2zAFFBk7uhVyPJVhAsqCWZptWfEPJxwfGDALQCcHmPdiwW2ONkwPz8F+tqrjG9oIzB9trUxzM/rd3HGcQi2skNBQmZZhE7+rpDEDnX7ugQLct6nwamqKEUI6ePEY\",\"fabricIndex\":1}],\"0/62/3\":1,\"0/62/65533\":1,\"0/62/4\":[\"FTABAQEkAgE3AyQUARgmBIAigScmBYAlTTo3BiQUARgkBwEkCAEwCUEEwepBAlEPJkAauIQf9vzb8eWFAd21uhY0+zBYGDsZ4Mqr+qt8U+ybU4Durk9Sjnt3q6tGa5YUZFi3ohayi6bInjcKNQEpARgkAmAwBBQZO7oVcjyVYQLKglmabVnxDyccHzAFFBk7uhVyPJVhAsqCWZptWfEPJxwfGDALQOvLkSUaWiMHrnJNE5Q/Lc8peLy8MmfrTihLgJE3RF+PQ4hlW5Cp+HaBUAjYdgwL0m0bgUkzp+hueqUWzYhepVsY\"],\"0/62/1\":[{\"rootPublicKey\":\"BMHqQQJRDyZAGriEH/b82/HlhQHdtboWNPswWBg7GeDKq/qrfFPsm1OA7q5PUo57d6urRmuWFGRYt6IWsoumyJ4=\",\"vendorID\":65521,\"fabricID\":1,\"nodeID\":2,\"label\":\"\",\"fabricIndex\":1}],\"0/62/65531\":[0,1,2,3,4,5,65528,65529,65531,65532,65533],\"0/62/5\":1,\"0/62/65532\":0,\"0/62/2\":16,\"0/62/65529\":[0,2,4,6,7,9,10,11],\"0/49/1\":[{\"networkID\":\"ZW5vMQ==\",\"connected\":true}],\"0/49/65529\":[],\"0/49/65531\":[0,1,2,3,4,5,6,7,65528,65529,65531,65532,65533],\"0/49/65533\":1,\"0/49/65532\":4,\"0/49/4\":true,\"0/49/2\":0,\"0/49/65528\":[],\"0/49/3\":0,\"0/49/0\":1,\"0/56/65529\":[0,1,2,4,5],\"0/56/65532\":11,\"0/56/6\":[],\"0/56/10\":2,\"0/56/12\":false,\"0/56/8\":0,\"0/56/65528\":[3],\"0/56/2\":0,\"0/56/65533\":2,\"0/56/65531\":[0,1,2,3,4,5,6,7,8,10,11,12,65528,65529,65531,65532,65533],\"0/56/5\":[{\"offset\":0,\"validAt\":0,\"name\":\"\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\\u0000\"}],\"0/56/1\":1,\"0/56/0\":751565917892086,\"0/56/11\":2,\"0/4294048774/65529\":[0,1],\"0/4294048774/65532\":0,\"0/4294048774/65533\":1,\"0/4294048774/65531\":[65528,65529,65531,65532,65533],\"0/4294048774/65528\":[]}"
	attributes = json.loads(myAttributesStr)

	jsonEndpoints = attributes_to_json(attributes)
	print(json.dumps(jsonEndpoints))
	cacheToDb(controllerId, '2', jsonEndpoints)

	deleteFromDb('mcc-thing-ver01-1', '2')

	conn.close()



if __name__ == "__main__":
	main_lambda_handler()