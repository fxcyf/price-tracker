frontend-build:
	cd ./frontend && pnpm build && cd ../
	
backend-build:
	docker compose -f docker-compose.yml -f docker-compose.prod.yml --project-name prod up -d --build