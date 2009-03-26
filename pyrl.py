#!/usr/bin/env python

import sys, socket, string, re, imp
import datetime
import twitter
import scheduler

# XXX: This is bad and shouldn't be done. But, encoding/deocoding stuff is annoying and I have
# a 10 month old son. ;)
reload(sys)
sys.setdefaultencoding('utf-8')

readbuffer = ''
alive = True
s = socket.socket()

def getConfig(fileName):
	"""reads in the config file and returns a configuration object"""
	config = imp.load_source('config', fileName + '.py')
	return config
	
def IRCconnect():
	"""This connects to the server"""
	s.connect((config.host, int(config.port)))
	s.send('NICK %s\r\n' % config.nick)
	s.send('USER %s %s bla :%s\r\n' % (config.ident, config.host, config.name))
	#for ch in config.channels:
	#	s.send('JOIN %s\r\n' % ch)
	s.send('JOIN %s\r\n' % config.channel)
	alive = True

def IRCdisconnect():
	#sendToChannel(config.channel, "The cake was a lie!")
	s.close()

def getApi():
	"""Create a twitter API instance when required"""
	api = twitter.Api(username=config.username, password=config.password)
	return api
  
def postToTwitter(channel, user, tweet):
	"""Post an update to twitter and return a URL to the update"""
	api = getApi()
	string = tweet + ' [' + user + ']'
	try:
		if len(string) <= 140:
			status = api.PostUpdate(string)
			url = ('http://twitter.com/%s/status/%s' % (config.username, status.id))
			msg = 'Posted: %s' % url
			sendToChannel(channel, msg)
		else:
			error = ('%s characters? That\'s way too long for a tweet. Don\'t be so verbose.' % len(string))
			sendToChannel(channel, error)
	except:
		sendToChannel(channel, "Error posting to twitter. Either twitter is down, there's an API problem, or that was a REALLY lame tweet.")

def postDirectMessage(channel, user, friend, tweet):
	"""Post a Direct Message to a user"""
	api = getApi()
	string = tweet + ' [' + user + ']'
	try:
		if len(string) <= 140:
			status = api.PostDirectMessage(friend, string)
			msg = 'Posted direct message to %s.' % friend
			sendToChannel(channel, msg)
		else:
			error = ('%s characters? That\'s way too long for a Direct Message. Don\'t be so verbose.' % len(string))
			sendToChannel(channel, error)
	except:
		print "Error posting direct message"
		#sendToChannel(channel, "Error posting to direct message. Either twitter is down, there's an API problem, or that was a REALLY lame tweet.")


def parseUser(string):
	"""Parse the user from the full user hostmask string"""
	try:
		user = re.compile(':(.*)!').search(string).group()
		return user[1:len(user)-1]
	except:
		return False
	
def getFollowing(channel):
	"""Get a list of twitter users that are being followed"""
	print "GetFollowing"
	api = getApi()
	try:
		users = api.GetFriends()
		f = [u.screen_name for u in users]
		sendToChannel(channel, string.join(f).replace(' ',', '))
	except:
		sendToChannel(channel, "Hurr")
	
def getFollowers(channel):
	"""Get a list of twitter users that are following"""
	api = getApi()
	try:
		users = api.GetFollowers()
		f = [u.screen_name for u in users]
		sendToChannel(channel, string.join(f).replace(' ',', '))
	except:
		sendToChannel(channel, "Hurr")

def addFriend(channel, user):
	"""Add the user as a friend"""
	api = getApi()
	try:
		friend = api.CreateFriendship(user)
		sendToChannel(channel, "Now following: %s" % friend.name)
	except:
		sendToChannel(channel, "Invalid user")
	
def removeFriend(channel, user):
	"""Remove a user from your friends list"""
	api = getApi()
	try:
		friend = api.DestroyFriendship(user)
		sendToChannel(channel, "No longer following: %s" % friend.name)
	except:
		sendToChannel(channel, "Not following: %s" % user)

# XXX: This is pretty lame. The timestamp of the last tweet is saved to a text file
def getLastTweet():
	"""Get the time of the last tweet"""
	f = open('lasttweet.db', 'r')
	created_at = float(f.read())
	f.close()
	return created_at
	
def setLastTweet(created_at):
	"""Set the time of the last tweet"""
	f = open('lasttweet.db', 'w')
	f.write(str(created_at))
	f.close()
	
def getLastDM():
	"""Get the time of the last direct message"""
	f = open('lastdm.db', 'r')
	created_at = float(f.read())
	f.close()
	return created_at

def setLastDM(created_at):
	"""Set the time of the last direct message"""
	f = open('lastdm.db', 'w')
	f.write(str(created_at))
	f.close()

def getTweets():
	"""Get your user timeline and show any new tweets"""
	print "getTweets()"
	api = getApi()
	channel = config.channel
	try:
		# Get our friends timeline and then reverse is so oldest is first
		tweets = api.GetFriendsTimeline()
		tweets.reverse()
		last_tweet = getLastTweet()
		for t in tweets:
			if t.created_at_in_seconds > last_tweet:
				# Don't announce the tweet if it's something we posted
				if t.user.screen_name != config.username:
					sendToChannel(channel, t.user.screen_name + ': ' + t.text)
				setLastTweet(t.created_at_in_seconds)
	except:
		print "Problem getting tweets"
		#sendToChannel(channel, "Problem getting tweets. It was probably twitter's fault.")

def getDirectMessages():
	"""Get your direct messages and show any that are new"""
	print "getDirectMessages()"
	api = getApi()
	channel = config.channel
	try:
		dms = api.GetDirectMessages()
		dms.reverse()
		last_dm = getLastDM()
		for d in dms:
			if d.created_at_in_seconds > last_dm:
				sendToChannel(channel, "Direct message from " + d.sender_screen_name + ': ' + d.text)
				setLastDM(d.created_at_in_seconds)
	except:
		print "Problem getting direct messages"
		#sendToChannel(channel, "Problem getting direct messages. It was probably twitter's fault.")

def getUser(channel, u):
	"""Get information about a user"""
	api = getApi()
	try:
		user = api.GetUser(u)
		msg = ('%s (%s). %s' % (user.name, user.location, user.description))
		sendToChannel(channel, msg)
	except:
		msg = "Sorry. Couldn't get user info for %s" % user
		sendToChannel(channel, msg)
		

def fetchTweets(channel, user, numTweets):
	"""Fetch the most recent X tweets for the specified user"""
	api = getApi()
	try:
		if numTweets > 20:
			numTweets = 1
		tweets = api.GetUserTimeline(user=user, count=numTweets)
		tweets.reverse()
		for t in tweets:
			sendToChannel(channel, t.text)
	except:
		msg = "Sorry. Couldn't fetch tweets for %s." % user
		sendToChannel(channel, msg)


def getHelp(channel, user):
	help_msg = """pyrl provides the following commands:
To find out information about a user:
	!who <name>
To get the last x tweets from a user:
	!fetch <name> [x]
To begin following someone:
	!follow <name>
To stop following someone:
	!unfollow <name>
To list all users that are being followed:
	!following
To list all users that are following:
	!followers
To post to twitter:
	!tweet <msg>
To send a direct message:
	!dm <friend> <msg>
The twitter timeline of those being followed will be checked periodically and updates will be sent to the channel.
Direct messages will also be checked and send to the channel."""
	for h in help_msg.split('\n'):
		sendToChannel(user, h)
	
	
def sendToChannel(channel, msg):
	"""Send the message to the channel"""
	s.send('PRIVMSG %s :%s\r\n' % (channel, msg))


# Load the configuration file
config = getConfig('config')
IRCconnect()

# Create a scheduler to download and post tweets
pScheduler = scheduler.Scheduler()

# Wait a little while, then check tweets every 2 minutes
soon = datetime.datetime.now() + datetime.timedelta(minutes=1)
getTweetsTask = scheduler.Task("getTweetsTask", 
							soon,
							scheduler.every_x_mins(2),
							func = getTweets)
getTweetsReceipt = pScheduler.schedule_task(getTweetsTask)

# Wait a little while, then check Direct Messages every 3 minutes
soon = datetime.datetime.now() + datetime.timedelta(minutes=2)
getDirectMessagesTask = scheduler.Task("getDirectMessagesTask", 
							soon,
							scheduler.every_x_mins(2),
							func = getDirectMessages)
getDMReceipt = pScheduler.schedule_task(getDirectMessagesTask)

pScheduler.start()

while (alive):
	# Read the buffer
	readbuffer = readbuffer + s.recv(500)
	temp = string.split(readbuffer, "\n")
	readbuffer = temp.pop( )
	#for line in temp:
	#	 parseIRC(line)
	for line in temp:
		print line
		line = string.rstrip(line)
		line = string.split(line)
		
		if(line[0] == "PING"):
			s.send("PONG %s\r\n" % line[1])
		
		
		if (len(line) >= 4 and parseUser(line[0]) not in config.blacklist):
			
			# Pick out the channel the message came from 
			# (so that multiple channels and Private Messages are supported)
			if line[2] == config.nick:
				channel = parseUser(line[0])
			else:
				channel = line[2]
				
			# Handle the !quit command from the owner
			# XXX: Add your name in here. Should be a config setting.
			if (line[3] == ':!quit'):
				if parseUser(line[0]) == 'ADMIN':
					alive = False
					
			# Handle a post to twitter		  
			if (line[3] == ':!tweet'):
				tweet = string.join(line[4:len(line)])
				user = parseUser(line[0])
				postToTwitter(channel, user, tweet)
				
			# Send a direct message
			if (line[3] == ':!dm'):
				if (len(line) > 5):
					user = parseUser(line[0])
					tweet = string.join(line[5:len(line)])
					friend = line[4]
					postDirectMessage(channel, user, friend, tweet)
			
			# Print a list of those who we are following
			if (line[3] == ':!following'):
				getFollowing(channel)
				
			# Print a list of those who are following us
			if (line[3] == ':!followers'):
				getFollowers(channel)
			
			# Start following/add friend
			if (line[3] == ':!follow' and len(line) > 4):
				addFriend(channel, line[4])
			
			# Stop following/remove friend
			if (line[3] == ':!unfollow' and len(line) > 4):
				removeFriend(channel, line[4])
			
			# Get information about a user
			if (line[3] == ':!who' and len(line) > 4):
				getUser(channel, line[4])
			
			# Fetch the most recent tweets from the user
			if (line[3] == ':!fetch' and len(line) > 4):
				try:
					numTweets = int(line[5])
				except:
					numTweets = 1
				fetchTweets(channel, line[4], numTweets)		
				
			if (line[3] == ':!help'):
				user = parseUser(line[0])
				getHelp(channel, user)
				
IRCdisconnect()

pScheduler.drop(getTweetsReceipt)
pScheduler.drop(getDMReceipt)
pScheduler.halt()
