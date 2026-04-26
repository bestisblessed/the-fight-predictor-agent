import os
import json

from flask import Flask, jsonify, request

from settings import Config
from service import FightAgentRuntime, build_runtime_bundle


def create_app(
    config: Config | None = None,
    responder=None,
    x_client=None,
    context_builder=None,
    start_worker: bool | None = None,
) -> Flask:
    runtime_config = config or Config.from_env()
    runtime_config.require_runtime()
    if start_worker is None:
        start_worker = os.getenv("OPTIMIZED_DISABLE_INPROCESS_WORKER") != "1"
    runtime = FightAgentRuntime(
        build_runtime_bundle(
            config=runtime_config,
            responder=responder,
            x_client=x_client,
            context_builder=context_builder,
        ),
        start_worker=start_worker,
    )

    app = Flask(__name__)
    app.runtime = runtime  # type: ignore[attr-defined]

    @app.get("/healthz")
    def healthz():
        return jsonify(app.runtime.health_payload())  # type: ignore[attr-defined]

    @app.get("/x/webhook")
    def crc_check():
        crc_token = request.args.get("crc_token", "").strip()
        if not crc_token:
            return jsonify({"error": "crc_token query parameter is required"}), 400
        response_token = app.runtime.bundle.x_client.crc_response_token(crc_token)  # type: ignore[attr-defined]
        return jsonify({"response_token": response_token})

    @app.post("/x/webhook")
    def webhook():
        raw_body = request.get_data(cache=False)
        signature = request.headers.get("x-twitter-webhooks-signature", "")
        if not app.runtime.bundle.x_client.verify_webhook_signature(raw_body, signature):  # type: ignore[attr-defined]
            return jsonify({"accepted": False, "error": "invalid signature"}), 401

        try:
            payload = json.loads(raw_body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            payload = None
        if not isinstance(payload, dict):
            return jsonify({"accepted": False, "error": "invalid JSON payload"}), 400

        record = app.runtime.state.append_inbox_payload(payload)  # type: ignore[attr-defined]
        app.runtime.enqueue_record(record)  # type: ignore[attr-defined]
        return jsonify({"accepted": True}), 200

    return app


if __name__ == "__main__":
    create_app().run(host="127.0.0.1", port=8080, debug=False)
