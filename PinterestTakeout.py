#
# Query images and metadata from Pinterest boards.
#
# Copyright (C) 2016  Oleksandr Dunayevskyy  <oleksandr.dunayevskyy@gmail.com>  
# Under MIT License.
#
# To install dependencies easy-way:
#     pip install --upgrade google-api-python-client
#

import oauth2client.client
import httplib2
import http.server
import socketserver
import ssl
import webbrowser
import urllib
import json

# enable debug logs for httplib
#httplib2.debuglevel = 4

# pretty printing of hierarchical data structures as json
def print_json(data):
	print(json.dumps(data, sort_keys=True, indent=4, separators=(',', ': ')))
	
#
# Launch a dummy HTTP server on localhost to receive the auth code 
# which is sent as part of GET request to redirect_uri.
# Note that we have set redirect_uri to https://localhost in Pinterest's app configuration.
#
def get_oauth_code():	
	class HttpRequestHandler(http.server.BaseHTTPRequestHandler):	
		keep_running = True
		auth_code = ""
		def do_GET(self):
			if HttpRequestHandler.keep_running:
				print("Received: ", self.command, self.path)				
				self.send_response(200)
				self.send_header('Content-type','text/html')
				self.end_headers()
				self.wfile.write( bytes("SUCCESS", "ISO-8859-1") )				
				HttpRequestHandler.auth_code = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)["code"][0]
				HttpRequestHandler.keep_running = False # set trigger condition for server to stop processing
	port = 443
	handler = HttpRequestHandler
	httpd = socketserver.TCPServer(("localhost", port), handler)
	httpd.socket = ssl.wrap_socket(httpd.socket, certfile="cert.pem", server_side=True)
	print("Running HTTP server at port", port)
	while HttpRequestHandler.keep_running: # process requests until condition is false
		httpd.handle_request()	
	httpd.server_close()
	# return the auth_code set in the handler
	return HttpRequestHandler.auth_code



#
# OAuth sequence
#


# Step 1: obtain authorization URL

flow = oauth2client.client.flow_from_clientsecrets(
	"client_secrets.json",
	scope='read_public',
	redirect_uri="https://localhost")

auth_url = flow.step1_get_authorize_url()

webbrowser.open_new(auth_url)

# Step 1.1 Code is sent via GET request to redirect_uri -- intercept it
code = get_oauth_code()

print("auth code =", code)

# Step 2: obtain access token

credentials = flow.step2_exchange(code)

http = httplib2.Http()
http = credentials.authorize(http)

print("access token =", credentials.get_access_token())


# 
# Authorized; now requests can be issued
#

def pinterest_get(http, path, cursor = None, fields = None):
	parameters = {"limit": 100 }
	if cursor:
		parameters["cursor"] = cursor
	if fields:
		parameters["fields"] = fields
	parameters_enc = urllib.parse.urlencode(parameters)
	url = "https://api.pinterest.com" + path + "?" + parameters_enc
	response = http.request(url, method="GET")
	response_str = response[1].decode("UTF-8")
	#print ("response_str", response_str)
	response_data = json.loads(response_str)
	#print_json(response_data)
	return response_data
	

# Requests all items by stiching results of multiple requests into a common list
# (single request can't return more than 25 items)
def pinterest_get_all(http, path, fields = None):
	cursor = None
	combined_response =  {"data": [] }
	while True:
		response = pinterest_get(http, path, cursor, fields)
		combined_response["data"].extend(response["data"])
		cursor = response["page"]["cursor"]
		print("cursor", cursor)
		if cursor == None:
			break
	print("result-size",  len(combined_response["data"]))
	return combined_response


class TakeoutBoard:
	def __init__(self, http):
		self.http = http
	def process(self,board):
		board_info = pinterest_get(self.http, "/v1/boards/" + board +"/")
		board_info_data = board_info["data"]

		board_pins = pinterest_get_all(self.http, "/v1/boards/" + board + "/pins/", fields = "url,image,link")
		#print_json(board_pin_links)
		board_pins_data = board_pins["data"]

		self.export_html(board, board_info_data, board_pins_data)
		
	def export_stdout(self, board, board_info, board_pins):
		print_json(board_info)
		print_json(board_pins)
	def export_html(self, board, board_info, board_pins):
		board_export_name= board.replace("/", "_")
		board_export_name_file = board_export_name + ".html"
		board_doc = open(board_export_name_file, "w")
		board_doc.write('<!DOCTYPE html PUBLIC "-//W3C//DTD HTML 4.01//EN" ')
		board_doc.write('"http://www.w3.org/TR/html4/strict.dtd">\n')
		board_doc.write('<html lang="en">\n')
		board_doc.write('<head>\n')
		board_doc.write('<meta http-equiv="content-type" content="text/html; charset=utf-8">\n')
		board_doc.write('<title>%s</title>\n' % board_info["name"] )
		board_doc.write('<link rel="stylesheet" type="text/css" href="style.css">\n')
		#board_doc.write('<script type="text/javascript" src="script.js"></script>\n')
		board_doc.write('</head>\n')
		board_doc.write('<body>\n')
		board_doc.write('<h1><a href="%s">%s</h1>\n' % (board_info["url"], board_info["name"]) )
		i = 0
		for item in board_pins:
			i = i + 1
			image= item["image"]["original"]
			board_doc.write('<!-- pin: %s -->\n' % item["id"])
			board_doc.write('<div class="item">\n')
			board_doc.write('	<div class="item_pic">\n')
			board_doc.write('		<a href="%s" target="_blank"><img src="%s" id="pin%d"></a>\n' % (item["url"], image["url"], i))
			board_doc.write('	</div>\n')
			board_doc.write('	<div class="item_desc">\n')
			board_doc.write('		%d / %d <a href="#pin%d" target="_blank">[#]</a>\n' % (i,len(board_pins), i) )
			board_doc.write('		&nbsp;&nbsp;<a href="%s" target="_blank">[Pin]</a>\n' % item["url"])
			board_doc.write('		&nbsp;<a href="%s" target="_blank">[Source]</a>\n' % item["link"])
			board_doc.write('	</div>\n')
			board_doc.write('</div>\n')
		board_doc.write('</body>\n')
		board_doc.write('</html>\n')
		board_doc.close()
		print("Exported", board_export_name_file)

takeout_board = TakeoutBoard(http)
#takeout_board.process("andymcpartland9/house")
takeout_board.process("staceycher/interiors-grey")
