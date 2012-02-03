# Quick and dirty IRC triviabot script

# - based somewhat on example code at http://www.osix.net/modules/article/?id=780
# - based on ircbot.ps by darkf
# - got some help from old stackoverflow page:
#   http://stackoverflow.com/questions/2719017/how-to-set-timeout-on-pythons-socket-recv-method

ircd = "some-irc-server.com"
port = 6667
chan = "#some-channel"
owner = "some-person"		# admin rights, for e.g. "!quit" command

import hint
import heuristic

import sys
import socket
import select
import string
import os
import math
import random
import time

scores = {owner: 0}		# username -> score dictionary
qid = 0				# current question
quest = []			# question table
ans = []			# answer table
qc = 0				# total question count
question_time = 0		# timestamp of last question asking
hint_timer = 0			# projected timestamp of next hint giving
waiting = 2			# bot state
timeout = time.time() + 10	# projected timestamp of next question asking
				# (initially, enough timeout to get connected to the ircd)
heur = ""			# accpeted question substring
skips = 0			# skip votes
skippers = []			# skip-voting users

throttle = time.time()		# !hint throttle timer

do_scores = 0			# !scores
score_throttle = time.time()	# !scores throttle timer

#########################################################################

count = 0

f = open("questions.txt", "r")
first = True
for line in f:
	if first:
		source = line		# first line is question source text
		first = False
	else:
		# even lines are questions, odd lines answers
		if count % 2 == 0:
			quest.append(line.split("\n")[0])
		else:
			ans.append(line.split("\n")[0])
		count += 1

f.close()
qc = count / 2

# shuffle question meta-indices
qnums = range(qc)
random.shuffle(qnums)

########################################################################

s = socket.socket()
s.connect((ircd, port))

print "connected"

s.send("NICK quizclown\r\nUSER quizclown 0 * :trivia quiz bot\r\nJOIN "+chan+"\r\n")

# check if an answer is good enough.
def good_enough(quote, ans):
	if quote.upper() == ans.upper() or (quote+"s").upper()==ans.upper() or quote.upper()==(ans+"s").upper():
		return 1
	else:
		return 0

def bot_say(str):
	s.send("PRIVMSG "+chan+" :"+str+"\r\n")

bot_say("Hello, I'm a bot that asks trivia questions.");
bot_say("Questions from: %s" % source)

s.setblocking(0)

while 1:
	# select trick owed to old stackoverflow discussion 
	ready = select.select([s], [], [], 1)
	if ready[0]:
		line = s.recv(1024)

		words = line.split(" ")

		if words[0]=='PING':
			s.send("PONG "+word[1]+"\r\n")
			
		if len(words)>2 and words[1]=='PRIVMSG':
			quote = line.split(":")[2]
			quote = quote.split("\r\n")[0]
	
			user = words[0].split(":")[1]
			user = user.split("!")[0]
	
			heur = heuristic.heuristic(ans[qnums[qid]])
			full_ans = heuristic.plain_question(ans[qnums[qid]])

			if good_enough(quote, full_ans) or (heur != "" and good_enough(quote, heur)):
				bot_say("%s got it right in %d seconds" % (user, time.time()-question_time))
				
				if user not in scores:
					scores[user] = 0
	
				scores[user] += 1
	
				qid += 1
				waiting = 2
				timeout = time.time() + 5
	
			if quote=="quizclown":
				if line.split(":")[3]!="":
					bot_say("%s: please don't talk to me directly" % user)
					bot_say("%s: i.e. just type your answers :)" % user)
	
			if quote=="!ask" and waiting==2:
				timeout = time.time()

			if quote=="!quit" and user==owner:
				bot_say("leaving immediately")
				sys.exit(1)

			if quote=="!hint":
				if time.time() >= throttle:
					hint_timer = time.time()
					throttle = time.time() + 3

			if (quote=="!scores" or quote=="!score") and do_scores == 0:
				if time.time() >= score_throttle:
					do_scores = 1
					score_throttle = time.time() + 5

			# this should check for concurrent user-votes
			if quote=="!skip":
				if(skippers.count(user) == 0):				
					skippers.append(user)					
					skips += 1
					if skips > 3:
						skips = 0
						skippers = []
						bot_say("skipping question "+str(qnums[qid]+1)+"")
                                		qid += 1       
	        	                        waiting = 2
        	        	                timeout = time.time() + 5				

	if qid >= qc:
		bot_say("This is all for the quiz.")
		max = 0
		key = "nobody"
		for x in scores:
			if scores[x] > max:
				max = scores[x]
				key = x
		if max > 0:
			bot_say("%s has the top score: %d" % (key, max))

		bot_say("cya later ~")

		sys.exit(1)


	if time.time() >= hint_timer and waiting==1:	
		hint = hint.make_hint(plain_question(ans[qnums[qid]]))	# hint v2
		bot_say("Hint: %s" % hint)
		hint_timer = time.time() + 10
		throttle = time.time() + 3

	if math.floor(time.time()) % 150 == 0 or do_scores == 1:
		bot_say("Scores")
		keylist = scores.keys()
		keylist.sort()
		for key in keylist:
			bot_say("%s: %d points" % (key, scores[key]))

		do_scores = 0
		score_throttle = time.time() + 5

	# timeout between questions. can be skipped
	# by using the "!ask" command.
	if waiting == 2:
		if time.time() >= timeout:
			waiting = 0

	# ready to ask a question !
	if waiting == 0:
		bot_say("%d: %s" % (qnums[qid]+1, quest[qnums[qid]]))
		question_time = time.time()
		hint_timer = time.time() + 8
		waiting = 1



