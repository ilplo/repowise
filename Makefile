.PHONY: start start-all restart restart-all stop stop-all logs

start start-all:
	./repowise start

restart restart-all:
	./repowise restart

stop stop-all:
	./repowise stop

logs:
	./repowise logs -f
