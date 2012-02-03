# Make random hints for trivia answers.
# For example, "This is the answer to the question"
# could become "..is .s t.. ..sw.r .. the qu...i.."
# (or something else if make_hint() is run again, it's random)

import random
import math

def make_hint(ans):
	hintable = []		# offsets of characters we may ellipsify
	x = 0
	while x < len(ans):
		if(str.isalpha(ans[x]) or str.isdigit(ans[x])):
			hintable.append(x)
		x += 1
	
	# we ceil to be safe if we have less than 8 chars :D
	qty = math.ceil(len(hintable) * 3.5/8.0)
	while len(hintable) > qty:
		ch = random.randint(0, len(hintable)-1)
		n = hintable[ch]
		ans = ans[:n] + '.' + ans[n+1:]		# thanks darkf
		del hintable[ch]
	
	return ans

