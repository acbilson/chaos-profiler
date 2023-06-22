# tests the profiler on local code and sends to an HTML page with pandoc
test:
	python -B profile.py | pandoc -f markdown -t html > test.html; open test.html
