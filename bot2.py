#!/usr/bin/env python
# Quick and dirty IRC triviabot script

testing = False		# test bot *offline* using stdin/stdout debug shell
lurkmode = False	# "lurk" mode - ask questions infrequently
exec_shell = False

# - based somewhat on example code at http://www.osix.net/modules/article/?id=780
# - based on ircbot.ps by darkf
# - got some help from reading old stackoverflow pages:
#   http://stackoverflow.com/questions/2719017/how-to-set-timeout-on-pythons-socket-recv-method
#   http://stackoverflow.com/questions/613183/python-sort-a-dictionary-by-value

import hints
import heuristic

import sys
import socket
import select
import string
import os
import math
import random
import time
import pickle

log_out = sys.stderr

# read configuration
conf = open("config.txt", "r")
ircd, port, chan, owner = [conf.readline().strip() for n in xrange(4)]
conf.close()
port = int(port)

# check for custom login script
use_custom_login = True
try:
	lscr = open("login-command.txt", "r")
	login_script = lscr.readline().strip()
	lscr.close()
except IOError:
	use_custom_login = False	

# bot state
ASK_QUESTION = 0		# ready to ask a new question
WAIT_ANSWER = 1			# waiting for an answer
PAUSE = 2			# delay between questions
SNOOZE = 3			# for when nobody is around
state = PAUSE

# setup variables
scores = {owner: 0}		# username -> score dictionary
question_number = 0		# current question
quest = []			# question table
ans = []			# answer table
qc = 0				# total question count
question_time = 0		# timestamp of last question asking
hint_timer = 0			# projected timestamp of next hint giving
rs_throttle = time.time()	# reshuffle throttle
info_throttle = time.time()	# !info command throttle

stfu = {owner: 0}		# how many times the bot told a person
				# not to use "quizclown: answer"

skip_stfu = {owner: 0}		# how many times the bot told a person
				# not to vote (!skip) twice

kicks = 0

last_sign_of_life = time.time()	# last time anything happened

last_ping = None

# projected timestamp of next question asking

if testing:
	timeout = time.time()
else:
	timeout = time.time() + 10	# enough time to get connected to the ircd

heur = ""			# accpeted question substring
skips = 0			# skip votes
skippers = []			# skip-voting users

hint_throttle = time.time()	# !hint throttle timer

do_scores = 0			# !scores
auto_scores = time.time() + 100	# periodical automatic scores showing
score_throttle = time.time()	# !scores throttle timer
#autosave_timer = time.time() + 60
autoclear_timer = time.time() + 360

#########################################################################

# read questions/answers database

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
def shuffle_questions():
	global qnums, shuffle_sta

	qnums = range(qc)
	shuffle_sta = random.getstate()
	random.shuffle(qnums)

shuffle_questions()

########################################################################


# check for saved game
try:
	sgam = open("sgam.pickle", "r")
	savedat = pickle.load(sgam)
	sgam.close()
	save_shuffle_sta = savedat["shuffle_sta"]
	question_number = savedat["question_number"]
	scores = savedat["scores"]
	stfu = savedat["stfu"]

	qnums = range(qc)
	random.setstate(save_shuffle_sta)
	random.shuffle(qnums)

	print >> log_out, "saved game loaded"
except IOError:
	print >> log_out, "no saved game found"


if testing:
	print >> log_out, "multiplayer trivia debugging shell"
	print >> log_out, "syntax: username [word [...]]"
	print >> log_out, ""
else:
	s = socket.socket()
	s.connect((ircd, port))
	print >> log_out, "connected"
	s.send("NICK quizclown\r\nUSER quizclown 0 * :trivia quiz bot\r\n")

	# custom identification script ?
	if use_custom_login:
		print >> log_out, "trying to log in..."
		s.send("%s\r\n" % login_script)
		time.sleep(25)
		print >> log_out, "should be logged in now"

	s.send("JOIN "+chan+"\r\n")
	s.setblocking(0)

# procedure to check if an answer is good enough.
def good_enough(quote, ans):
	if quote.upper() == ans.upper() or (quote+"s").upper()==ans.upper() or quote.upper()==(ans+"s").upper():
		return 1
	else:
		return 0

def bot_say(str):
	if testing:
		print >> log_out, str
	else:
		s.send("PRIVMSG "+chan+" :"+str+"\r\n")

bot_say("I'm a triviabot. Type !info for details")

def print_info():
	bot_say("code: https://github.com/bl0ckeduser/quizclown/")
	bot_say("commands: https://raw.github.com/bl0ckeduser/quizclown/master/COMMANDS.txt")
	bot_say("question source: %s" % source)
	if lurkmode:
		bot_say("the bot is in 'lurk' (low question frequency) mode")


def save_game():
	global sgam

	sgam = open("sgam.pickle", "w")
	pickle.dump({"shuffle_sta": shuffle_sta, "question_number": question_number, "scores": scores, "stfu": stfu}, sgam)
	sgam.close()
	print >> log_out, "saved game"

def clear_scores():
	global scores

	if state != SNOOZE:
		bot_say("Cleared scores")
	scores = {owner: 0}

if exec_shell:
	print("python exec shell:")
	sys.stdout.write("% ")
	sys.stdout.flush()

while 1:
	if not testing:
		if exec_shell:
			shell_ready = select.select([sys.stdin], [], [], 1)
		ready = select.select([s], [], [], 1)
	else:
		ready = select.select([sys.stdin], [], [], 1)	
	
	if exec_shell:
		if shell_ready[0]:
			command = raw_input()
			print >> log_out, "running '%s'" % command
			try:
				exec(command)
			except:
				print "error in command"
			sys.stdout.flush()
			sys.stdout.write("% ")
			sys.stdout.flush()


	# if nothing's been happening for too long,
	# snooze.
	if time.time() - last_sign_of_life > 70:
		if state != SNOOZE:
			# start snooze
			bot_say("Snoozing")
			state = SNOOZE
	elif state == SNOOZE:
		# wake up from snooze
		# restate current question in 3 seconds.
		state = PAUSE
		timeout = time.time() + 3

	# If the network has been completely dead
	# for over 10 minutes, hang up and leave.
	if time.time() - max(last_sign_of_life, last_ping) > 60 * 10:
		print >> log_out, "Network dead. Hanging up."
		save_game()
		sys.exit(0)

	if ready[0]:
		if testing:
			# local debug shell - parse command
			comlin = raw_input()
			if len(comlin.split(" ")) > 1:
				cuser = comlin.split(" ")[0]
				ctext = comlin[comlin.find(" ")+1:]
				line = ":"+cuser+" PRIVMSG "+chan+" :" + ctext + "\r\n"
			else:
				line = ""
		else:
			line = s.recv(1024)

		print >> log_out, "> %s" % line

		words = line.split(" ")

		if len(words) > 0 and words[0] != 'PING':
			# something happened
			last_sign_of_life = time.time()

		if words[0]=='PING' and not testing:
			last_ping = time.time()
			s.send("PONG "+words[1]+"\r\n")

		# :long-nick KICK #channel quizclown :reason
		if len(words) > 2 and words[1]=='KICK' and words[3] == 'quizclown':
			print >> log_out, "got kicked :( ... saving game ..."
			save_game()	# for convenience
			kicks += 1
			if kicks > 3:
				print >> log_out, "too many kicks; quitting"
				sys.exit(1)
			time.sleep(3)
			print >> log_out, "rejoining now"
			s.send("JOIN "+chan+"\r\n")

		if len(words) > 2 and words[1]=='NICK':
			# When a nick change occurs, update
			# score table with new nick
			user = words[0].split(":")[1]
			user = user.split("!")[0]
			new_nick = ":".join(line.split(":")[2:])
			new_nick = new_nick.split("\r\n")[0]
			print >> log_out, "%s -> %s" % (user, new_nick)
			if user in scores:
				if new_nick not in scores:
					scores[new_nick] = scores[user]
				else:
					scores[new_nick] += scores[user]

				del scores[user]


		# hack to allow owner to issue commands in private
		# (useful if e.g. the bot gets kicked)
		if len(words)>2 and words[1]=='PRIVMSG' and words[2]!=chan:
			if len(words[0].split(":")) > 1:
				user = words[0].split(":")[1]
				user = user.split("!")[0]
				if user == owner:
					words[2] = chan

		if len(words)>2 and words[1]=='PRIVMSG' and words[2]==chan:
			# somebody said something in the channel
			quote = ":".join(line.split(":")[2:])
			quote = quote.split("\r\n")[0]
	
			user = words[0].split(":")[1]
			user = user.split("!")[0]
	
			heur = heuristic.heuristic(ans[qnums[question_number]])
			full_ans = heuristic.plain_question(ans[qnums[question_number]])

			# was it a correct answer ?
			if good_enough(quote, full_ans) or (heur != "" and good_enough(quote, heur)):
				bot_say("%s got it right in %d seconds" % (user, time.time()-question_time))
				
				if user not in scores:
					scores[user] = 0
	
				scores[user] += 1
	
				question_number += 1
				state = PAUSE
				if lurkmode:
					timeout = time.time() + random.randrange(60, 100)			
				else:
					timeout = time.time() + random.randrange(5, 10)
		
			# was it a command ?

			if (quote=="!ask" or quote=="!next") and state==PAUSE:
				state = ASK_QUESTION

			if quote=="!squit":
				if user==owner:
					# save and quit
					save_game()
					bot_say("Game saved; leaving")
					sys.exit(0)

			if quote=="!quit":
				if user==owner:
					bot_say("Leaving immediately")
					sys.exit(0)

			if quote=="!hint":
				if time.time() >= hint_throttle:
					hint_timer = time.time()
					hint_throttle = time.time() + 3

			if quote=="!scores" or quote=="!score":
				do_scores = 1

			if quote == "!fskip" and user == owner and state == WAIT_ANSWER:
				skips = len(scores) + 1
				if owner in skippers:
					skippers.remove(user)
				quote = "!skip"

			if (quote=="!skip" or quote=="!next") and state==WAIT_ANSWER:
				if user in skippers:
					if user not in skip_stfu:
						skip_stfu[user] = 1
					else:
						skip_stfu[user] += 1
					if skip_stfu[user] == 1:
						bot_say("%s: you can't vote twice!" % user)
					elif skip_stfu[user] == 2:
						bot_say("%s: for the second and last time, you cannot vote twice." % user)
				else:
					skippers.append(user)					
					skips += 1
					if len(scores)/3 - skips == 1:
						bot_say("Need one more vote to skip this question")
					elif len(scores)/3 - skips > 0:
						bot_say("Need %d more votes to skip this question" % (len(scores)/3 - skips))
					if skips >= (len(scores)/3):
						# got enough votes - skip the question
						skips = 0
						skippers = []
						skip_stfu = {owner: 0}
						bot_say("skipping question "+str(qnums[question_number]+1)+"")
                                		question_number += 1       
	        	                        state = PAUSE
						if lurkmode:
							timeout = time.time() + random.randrange(60, 200)			
						else:
							timeout = time.time() + random.randrange(5, 10)

			if quote=="!reshuffle" and time.time() >= rs_throttle:
				bot_say("Reshuffling questions ...")
				shuffle_questions()
				question_number = 0
				state = ASK_QUESTION
				rs_throttle = time.time() + 150

			if quote == "!info" and time.time() >= info_throttle:
				info_throttle = time.time() + 60
				print_info()

			if quote == "!clear":
				if user == owner:
					clear_scores()

			if len(quote.split(":")) > 1 and quote.split(":")[0]=="quizclown":
				# the stfu cruft prevents abuse of this

				if user not in stfu:
					stfu[user] = 1
				else:
					stfu[user] += 1

				if stfu[user] == 1:
					bot_say("%s: please just type your answers, without typing my name" % user)
				elif stfu[user] == 2:
					bot_say("%s: for the second time, please do not type my name like that. I ignore these lines." % user)


	# Done with the questions, reshuffle and restart
	if question_number >= qc:
		bot_say("Reshuffling questions ...")
		shuffle_questions()
		question_number = 0
		state = ASK_QUESTION
		rs_throttle = time.time() + 150

	if time.time() >= hint_timer and state==WAIT_ANSWER:	
		hint = hints.make_hint(heuristic.plain_question(ans[qnums[question_number]]))
		bot_say("Hint: %s" % hint)
		hint_timer = time.time() + 12
		hint_throttle = time.time() + 3

	if time.time() >= score_throttle and do_scores:
		if sum(scores.values()) == 0:
			bot_say("No score yet")
		else:
			n = 0
			scorebuf = "Scores -- "

			for player in sorted(scores, key=scores.get, reverse=True):
				if scores[player] > 1:
					scoreline = "%s: %d pts" % (player, scores[player])
				elif scores[player] > 0:
					scoreline = "%s: %d pt" % (player, scores[player])
				else: continue

				if n > 0:
					scorebuf += ";   "
				scorebuf += scoreline

				# we display three scores per line
				n += 1
				if n % 3 == 0:
					n = 0
					bot_say(scorebuf)
					scorebuf = ""

			# flush scores buffer
			if scorebuf != "":
				bot_say(scorebuf)

		score_throttle = time.time() + 10

#	if time.time() > autosave_timer:
#		autosave_timer = time.time() + 120
#		save_game()
#		print >> log_out, "autosaved game"

	if time.time() > autoclear_timer:
		autoclear_timer = time.time() + 360
		clear_scores()

	# Clear score request register even if no scores were displayed --
	# it's best to discard throttled requests.
	do_scores = 0
	
	if time.time() >= auto_scores and state != SNOOZE:
		# for the players' convenience, we
		# automatically call the "!score" command
		# every N seconds.
		if lurkmode:
			auto_scores = time.time() + 300
		else:
			auto_scores = time.time() + 200
		do_scores = 1

	# delay between questions
	if state == PAUSE and time.time() >= timeout:
		state = ASK_QUESTION

	# ready to ask a question !
	if state == ASK_QUESTION:
		bot_say("%d: %s" % (qnums[question_number]+1, quest[qnums[question_number]]))
		question_time = time.time()
		hint_timer = time.time() + 8
		state = WAIT_ANSWER

	
