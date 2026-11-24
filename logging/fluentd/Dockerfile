FROM fluent/fluentd:v1.17-debian-1
USER root
RUN gem install --no-document fluent-plugin-elasticsearch -v 5.4.3 \
 && gem sources --clear-all
USER fluent
