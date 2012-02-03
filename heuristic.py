# Parse substring valid answers from moxquizz-style question data

# The original idea was that a "heuristic" could be made
# that found valid answer substrings itself, but this never
# happened.

def heuristic(lin):
	if '#' in lin:
		return lin.split("#")[1]
		print heur
	else:
		return ""

def plain_question(lin):
	return lin.replace('#', '')

