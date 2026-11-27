FROM fluent/fluentd:v1.17-debian-1
USER root
RUN gem install --no-document fluent-plugin-elasticsearch -v 5.4.3 \
 && gem sources --clear-all
USER fluent
USER root
# Keep the Ruby client compatible with the Elasticsearch 8.x server.
RUN gem install --no-document elasticsearch -v 8.15.0 \
 && gem uninstall --all --executables --ignore-dependencies -v '>= 9' elasticsearch elasticsearch-api
USER fluent
