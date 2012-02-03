# Converts moxquizz datafiles to the quizclown
# format. moxzquizz substring answers are preserved
# and parsed by quizclown itself.

# untar the moxquizz database in the quizclown
# and then do
#	$ python import-moxquizz.py > questions.txt
# to import the moxquizz questions into quizclown.

f = open("moxquizz/quizdata/questions.trivia.en", "r")

print "GPL'd Moxquizz database"

for line in f:
	if str.find(line, "Question:") != -1:
		print line.split("Question: ")[1].split("\n")[0]

	if str.find(line, "Answer:") != -1:
		lin = line.split("Answer: ")[1].split("\n")[0]
		print lin

f.close()
