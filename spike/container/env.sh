#!/bin/sh
# Write Rallly's two .env files for a toolchain that runs inside a
# container on the compose stack's own network, where the services are
# reachable by name rather than on localhost. Run on the host, from the
# clone's root, once; it never overwrites an existing .env.
#
# Every value here comes from the pinned checkout's docker-compose.dev.yml
# and .env.sample files. When the pin moves, re-check the service names,
# the internal ports, and the keys.
set -eu
[ -f docker-compose.dev.yml ] || { echo "run this from the Rallly clone's root"; exit 1; }

write() { # write <sample> <target> : copy unless target exists, then rewrite hosts in place
  if [ -f "$2" ]; then echo "$2 exists; leaving it alone"; return; fi
  cp "$1" "$2"
  sed -i \
    -e 's#^DATABASE_URL=postgres://postgres:postgres@localhost:5450/rallly#DATABASE_URL=postgres://postgres:postgres@rallly_db:5432/rallly#' \
    -e 's#^KV_REST_API_URL=http://0\.0\.0\.0:8079#KV_REST_API_URL=http://serverless-redis-http:80#' \
    -e 's#^SMTP_HOST=0\.0\.0\.0#SMTP_HOST=mailpit#' \
    -e 's#^S3_ENDPOINT=http://localhost:3900#S3_ENDPOINT=http://garage:3900#' \
    -e 's#^NEXT_PUBLIC_BASE_URL=https://web\.rallly\.test#NEXT_PUBLIC_BASE_URL=http://localhost:3000#' \
    "$2"
  if grep -q '^SECRET_PASSWORD=$' "$2"; then
    secret=$(head -c 32 /dev/urandom | od -An -tx1 | tr -d ' \n')
    [ ${#secret} -eq 64 ] || { echo "could not generate a secret"; exit 1; }
    sed -i "s/^SECRET_PASSWORD=$/SECRET_PASSWORD=$secret/" "$2"
  fi
  echo "wrote $2"
}

write apps/web/.env.sample apps/web/.env
write packages/database/.env.sample packages/database/.env
echo "services: rallly_db:5432 serverless-redis-http:80 mailpit:1025 garage:3900; app at http://localhost:3000"
