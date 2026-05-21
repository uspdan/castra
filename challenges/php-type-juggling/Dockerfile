FROM php:8.2-apache

COPY index.php /var/www/html/index.php
COPY style.css /var/www/html/style.css


# Sealed answer + flag sidecars staged by scripts/stage-answers.sh
# before docker build. Root-owned, mode 0600 inside the image —
# readable by the validator (root) and unreadable by the player
# (hunter).
COPY .answers.json /opt/answers.json
COPY .flag.txt /opt/flag.txt

RUN chmod 600 /opt/answers.json /opt/flag.txt && \
    chown root:root /opt/answers.json /opt/flag.txt

EXPOSE 80
CMD ["apache2-foreground"]
