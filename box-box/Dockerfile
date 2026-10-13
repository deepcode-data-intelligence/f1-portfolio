FROM rust:1-bookworm AS build
WORKDIR /src
COPY Cargo.toml Cargo.lock ./
COPY src ./src
RUN cargo build --release --locked

FROM debian:bookworm-slim
RUN useradd -r -u 10001 boxbox && mkdir -p /data && chown boxbox /data
COPY --from=build /src/target/release/box-box /usr/local/bin/box-box
USER boxbox
ENV BOXBOX_BIND=0.0.0.0:8081 BOXBOX_DATA_DIR=/data
EXPOSE 8081
VOLUME ["/data"]
ENTRYPOINT ["box-box"]
