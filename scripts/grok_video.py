#!/usr/bin/env python3
"""One-step async video jobs with durable, duplicate-safe submission receipts."""
import argparse
import base64
import hashlib
import json
import mimetypes
import os
from pathlib import Path
import sys
import time
from urllib import error, parse, request


class NoRedirect(request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        return None


class JobError(Exception):
    pass


def write_private(path, data, exclusive=False):
    raw = (json.dumps(data, ensure_ascii=False, indent=2) + '\n').encode()
    path.parent.mkdir(parents=True, exist_ok=True)
    if exclusive:
        fd = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
    else:
        temp = path.with_name(path.name + '.tmp')
        fd = os.open(temp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
        with os.fdopen(fd, 'wb') as f:
            f.write(raw); f.flush(); os.fsync(f.fileno())
        temp.replace(path)


def build(spec_file):
    spec_file = Path(spec_file).resolve(strict=True)
    spec = json.loads(spec_file.read_text())
    base = str(spec['base_url']).rstrip('/')
    parsed = parse.urlsplit(base)
    if parsed.scheme not in ('https', 'http') or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
        raise JobError('base_url must be an HTTP(S) API root without credentials, query or fragment')
    duration = float(spec['duration'])
    if not duration > 0 or duration == float('inf'):
        raise JobError('duration must be finite and positive')
    prompt = (spec_file.parent / spec['prompt_file']).read_text().strip()
    if not prompt:
        raise JobError('Empty prompt')
    payload = {k: spec[k] for k in ('model', 'duration', 'resolution', 'aspect_ratio')}
    payload['duration'] = duration
    if any(not isinstance(payload[k], str) or not payload[k] for k in ('model', 'resolution', 'aspect_ratio')):
        raise JobError('model, resolution and aspect_ratio must be nonempty strings')
    payload['prompt'] = prompt
    inputs = []

    def img(name, role):
        path = (spec_file.parent / name).resolve(strict=True)
        mime = mimetypes.guess_type(path.name)[0]
        if mime not in ('image/jpeg', 'image/png', 'image/webp'):
            raise JobError('Use JPEG, PNG or WebP reference images')
        raw = path.read_bytes()
        if not raw:
            raise JobError('Empty reference image')
        inputs.append({'role': role, 'file': str(path), 'sha256': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw)})
        return {'url': f'data:{mime};base64,' + base64.b64encode(raw).decode()}

    for field in ('image', 'last_frame'):
        if spec.get(field): payload[field] = img(spec[field], field)
    last = -1.0
    for i, frame in enumerate(spec.get('keyframes', [])):
        stamp = float(frame['timestamp_s'])
        if not 0 < stamp < duration or stamp <= last:
            raise JobError('Keyframe timestamps must increase strictly inside (0, duration)')
        last = stamp
        payload.setdefault('keyframes', []).append({'image': img(frame['image'], f'keyframe-{i}'), 'timestamp_s': stamp})
    fingerprint = hashlib.sha256(json.dumps({'base_url': base, 'payload': payload}, sort_keys=True, separators=(',', ':')).encode()).hexdigest()
    public = {k: v for k, v in payload.items() if k not in ('image', 'last_frame', 'keyframes')}
    public.update({'base_url': base, 'inputs': inputs, 'fingerprint': fingerprint,
                   'keyframe_times_s': [f['timestamp_s'] for f in payload.get('keyframes', [])]})
    return base, payload, public


def api(base, path, key, payload=None):
    body = json.dumps(payload).encode() if payload is not None else None
    req = request.Request(base+path, data=body,
                          headers={'Authorization': 'Bearer '+key, 'Content-Type': 'application/json', 'Accept': 'application/json'},
                          method='POST' if payload is not None else 'GET')
    # Never redirect an authenticated API call to another host.
    with request.build_opener(NoRedirect).open(req, timeout=55) as response:
        raw = response.read(2*1024*1024+1)
        if len(raw) > 2*1024*1024:
            raise JobError('Oversized API receipt')
        return json.loads(raw)


def read_state(path, fingerprint):
    state = json.loads(path.read_text())
    if state.get('fingerprint') != fingerprint:
        raise JobError('Input or provider changed. Use a new version and a new state file.')
    return state


def summary(state):
    return {k: state[k] for k in ('status', 'provider_status', 'request_id', 'fingerprint', 'http_status', 'error_kind', 'output_file', 'output_sha256') if k in state}


def execute(args):
    base, payload, public = build(args.spec)
    path = Path(args.state).resolve()
    fp = public['fingerprint']
    if args.command == 'prepare':
        return public
    # Existing state is authoritative; a second submit never makes a POST.
    if args.command == 'submit' and path.exists():
        state = read_state(path, fp)
        if not state.get('request_id'):
            raise JobError('Existing submission has no confirmed ID; reconcile with provider. Do not resubmit this state.')
        return summary(state)
    if args.command != 'submit':
        state = read_state(path, fp)
    if args.command == 'attach-id':
        if state.get('request_id') or state.get('status') != 'submit_uncertain':
            raise JobError('Can attach an ID only to an unresolved submission')
        if not args.request_id:
            raise JobError('--request-id from provider records is required')
        state.update({'request_id': args.request_id, 'status': 'pending', 'id_recovered_at': time.time()})
        write_private(path, state)
        return summary(state)
    if args.command == 'download':
        if state.get('status') != 'done' or not state.get('result_url'):
            raise JobError('No completed result URL; poll the known request first')
        if not args.out:
            raise JobError('--out is required')
        out = Path(args.out).resolve()
        if out.exists():
            if state.get('output_file') == str(out) and state.get('output_sha256') == hashlib.sha256(out.read_bytes()).hexdigest():
                return summary(state)
            raise JobError('Output exists; choose a versioned name')
        url = parse.urlsplit(state['result_url'])
        if url.scheme not in ('http', 'https') or not url.hostname or url.username or url.password:
            raise JobError('Unexpected result URL')
        out.parent.mkdir(parents=True, exist_ok=True)
        temp = out.with_name(out.name + '.part')
        digest = hashlib.sha256()
        # Deliberately no Authorization header on a media URL or its redirects.
        with request.urlopen(state['result_url'], timeout=55) as response, temp.open('wb') as dst:
            first = response.read(1024)
            if b'ftyp' not in first[:64]:
                raise JobError('Expected MP4 media, got a non-MP4 response')
            dst.write(first); digest.update(first)
            while True:
                chunk = response.read(1024*1024)
                if not chunk: break
                dst.write(chunk); digest.update(chunk)
            dst.flush(); os.fsync(dst.fileno())
        # Same-directory link publishes atomically and refuses an existing output.
        os.link(temp, out)
        temp.unlink()
        state.update({'output_file': str(out), 'output_sha256': digest.hexdigest()})
        write_private(path, state)
        return summary(state)
    key = os.environ.get(args.key_env)
    if not key:
        raise JobError(f'Set {args.key_env} locally; do not paste credentials in chat')
    if args.command == 'submit':
        state = {'fingerprint': fp, 'status': 'submit_uncertain', 'submitted_at': time.time(), 'request': public}
        write_private(path, state, exclusive=True)
        try:
            response = api(base, '/videos/generations', key, payload)
            job_id = response.get('request_id') or response.get('id')
            if not isinstance(job_id, str) or not job_id:
                raise JobError('No confirmed request ID')
            state.update({'request_id': job_id, 'status': 'pending'})
        except error.HTTPError as exc:
            state.update({'http_status': exc.code, 'error_kind': 'http_error'})
            if exc.code in (400, 401, 403, 404, 413, 422): state['status'] = 'rejected'
            write_private(path, state)
            raise JobError(f'Submit HTTP {exc.code}; state={state["status"]}. No automatic resubmission.')
        except Exception as exc:
            state['error_kind'] = type(exc).__name__
            write_private(path, state)
            raise JobError('Submission outcome uncertain; reconcile the saved job before retrying') from None
        write_private(path, state)
        return summary(state)
    if args.command == 'poll':
        if not state.get('request_id'):
            raise JobError('No known request ID; reconcile the submission first')
        if state['status'] == 'failed' or (state['status'] == 'done' and not args.refresh):
            return summary(state)
        response = api(base, '/videos/'+parse.quote(state['request_id'], safe=''), key)
        status = str(response.get('status', '')).lower()
        video = response.get('video') or {}
        if status in ('done', 'completed', 'succeeded') and isinstance(video, dict) and video.get('url'):
            state.update({'status': 'done', 'result_url': video['url']})
        elif status in ('failed', 'error', 'cancelled', 'canceled'):
            state['status'] = 'failed'
        else:
            state['status'] = 'pending'
        state['provider_status'] = status
        state['checked_at'] = time.time()
        write_private(path, state)
        return summary(state)
    raise JobError('Unknown command')


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('command', choices=['prepare', 'submit', 'poll', 'download', 'attach-id'])
    p.add_argument('spec'); p.add_argument('--state', default='job-state.json')
    p.add_argument('--key-env', default='VIDEO_API_KEY'); p.add_argument('--out'); p.add_argument('--request-id')
    p.add_argument('--refresh', action='store_true', help='Re-query a completed job for a fresh media URL')
    args = p.parse_args()
    try:
        result = execute(args)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get('status') in ('failed', 'rejected', 'submit_uncertain') else 0
    except (JobError, OSError, ValueError, KeyError, TypeError) as exc:
        # HTTP bodies, signed URLs and authenticated Request objects must not be printed.
        if isinstance(exc, error.HTTPError): message = f'HTTP {exc.code}; saved job unchanged, retry this operation only'
        elif isinstance(exc, error.URLError): message = 'Network error; saved job unchanged, retry this operation only'
        else: message = str(exc)
        print(message, file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
