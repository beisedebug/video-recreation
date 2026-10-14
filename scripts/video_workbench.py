#!/usr/bin/env python3
"""Local, deterministic media helpers. FFmpeg required; ffprobe optional."""
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
from fractions import Fraction
from pathlib import Path


def run(args):
    result = subprocess.run([str(x) for x in args], capture_output=True, text=True)
    if result.returncode:
        raise ValueError(result.stderr[-5000:] or 'Command failed')
    return result


def save(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + '.tmp')
    temp.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n')
    temp.replace(path)


def ratio(value):
    result = Fraction(str(value))
    if result <= 0:
        raise ValueError('Expected positive rate')
    return result


def probe(file):
    file = Path(file).resolve(strict=True)
    if shutil.which('ffprobe'):
        data = json.loads(run(['ffprobe', '-v', 'error', '-show_streams',
                               '-show_format', '-of', 'json', file]).stdout)
        streams = data.get('streams', [])
        videos = [s for s in streams if s.get('codec_type') == 'video'
                  and not s.get('disposition', {}).get('attached_pic')]
        if not videos:
            raise ValueError('No primary video stream')
        v = videos[0]
        fps = v.get('avg_frame_rate', '0/0')
        if fps in ('0/0', '0'):
            fps = v.get('r_frame_rate', '0/0')
        return {'path': str(file), 'backend': 'ffprobe', 'width': v['width'],
                'height': v['height'], 'fps': fps,
                'duration_s': float(v.get('duration') or data.get('format', {}).get('duration', 0)),
                'audio_streams': sum(s.get('codec_type') == 'audio' for s in streams),
                'rotation': next((s.get('rotation') for s in v.get('side_data_list', [])
                                  if 'rotation' in s), v.get('tags', {}).get('rotate', 0)),
                'nb_frames_metadata': v.get('nb_frames'),
                'avg_frame_rate': v.get('avg_frame_rate'),
                'r_frame_rate': v.get('r_frame_rate')}
    p = subprocess.run(['ffmpeg', '-hide_banner', '-i', str(file)], capture_output=True, text=True)
    lines = p.stderr.splitlines()
    v = next((x for x in lines if 'Stream #' in x and 'Video:' in x and 'attached pic' not in x), None)
    if not v:
        raise ValueError('No primary video stream: ' + p.stderr[-1000:])
    size = re.search(r'(?:^|[ ,])(\d{1,5})x(\d{1,5})(?=[ ,\[])', v)
    fps = re.search(r'([\d.]+) fps', v)
    duration = re.search(r'Duration: (\d+):(\d+):([\d.]+)', p.stderr)
    if not size or not fps:
        raise ValueError('FFmpeg fallback could not determine size/fps; install ffprobe')
    return {'path': str(file), 'backend': 'ffmpeg-stderr',
            'width': int(size[1]), 'height': int(size[2]), 'fps': fps[1],
            'duration_s': (int(duration[1])*3600 + int(duration[2])*60 + float(duration[3])) if duration else 0,
            'audio_streams': sum('Stream #' in x and 'Audio:' in x for x in lines),
            'rotation': None, 'note': 'Fallback metadata is approximate; rotation/VFR not fully inspected.'}


def sample(args):
    from PIL import Image, ImageDraw
    info = probe(args.video)
    step = args.step if args.step is not None else max(1, round(float(ratio(info['fps']))))
    end = args.end_frame
    if end is None:
        end = math.ceil(info['duration_s'] * float(ratio(info['fps'])))
    if args.start_frame < 0 or end <= args.start_frame or step < 1:
        raise ValueError('Invalid frame interval or step')
    count = math.ceil((end - args.start_frame) / step)
    if count > args.max_frames:
        raise ValueError(f'{count} samples exceeds --max-frames {args.max_frames}; narrow interval or increase step')
    out = Path(args.out_dir).resolve()
    out.mkdir(parents=True, exist_ok=False)
    vf = (f'select=between(n\\,{args.start_frame}\\,{end-1})*'
          f'not(mod(n-{args.start_frame}\\,{step})),scale=640:640:force_original_aspect_ratio=decrease,showinfo')
    result = run(['ffmpeg', '-hide_banner', '-i', args.video, '-map', '0:V:0', '-an',
                  '-vf', vf, '-fps_mode', 'vfr', '-frames:v', count, '-start_number', '0', out/'frame-%05d.png'])
    pts = re.findall(r'\bn:\s*\d+\s+pts:\s*\S+\s+pts_time:([\d.eE+\-]+)', result.stderr)
    files = sorted(out.glob('frame-*.png'))
    if not files or len(pts) != len(files):
        raise ValueError('Missing frames or timestamp alignment; inspect FFmpeg output')
    index = [{'file': f.name, 'source_frame': args.start_frame+i*step,
              'pts_s': float(pts[i])} for i, f in enumerate(files)]
    sheets = []
    for offset in range(0, len(files), 48):
        batch = files[offset:offset+48]
        sheet = Image.new('RGB', (6*200, math.ceil(len(batch)/6)*220), '#202020')
        draw = ImageDraw.Draw(sheet)
        for j, file in enumerate(batch):
            with Image.open(file) as im:
                thumb = im.convert('RGB')
                thumb.thumbnail((194, 190))
            x, y = (j % 6)*200, (j // 6)*220
            sheet.paste(thumb, (x+(200-thumb.width)//2, y))
            row = index[offset+j]
            draw.text((x+4, y+195), f"f{row['source_frame']}  {row['pts_s']:.3f}s", fill='white')
        name = f'contact-{offset//48+1:03d}.jpg'
        sheet.save(out/name, quality=88)
        sheets.append(name)
    report = {'source': info, 'frames': index, 'contact_sheets': sheets}
    save(out/'index.json', report)
    return {'directory': str(out), 'samples': len(files), 'contact_sheets': sheets}


def project(path):
    path = Path(path).resolve(strict=True)
    data = json.loads(path.read_text())
    if data.get('mode') not in ('recreate', 'transition', 'reedit'):
        raise ValueError('mode must be recreate, transition or reedit')
    fps = ratio(data['fps'])
    for key in ('width', 'height'):
        if type(data[key]) is not int or data[key] < 2 or data[key] % 2:
            raise ValueError(key + ' must be a positive even integer')
    if data.get('fit', 'cover') not in ('cover', 'contain'):
        raise ValueError('fit must be cover or contain')
    if 'audio' not in data:
        raise ValueError('Set audio to null (silent) or an explicit file specification')
    cursor, seen = 0, set()
    clips = data.get('clips', [])
    if not clips:
        raise ValueError('No clips')
    for clip in clips:
        if clip['id'] in seen:
            raise ValueError('Duplicate clip id')
        seen.add(clip['id'])
        if type(clip['target_frames']) is not int or clip['target_frames'] < 1:
            raise ValueError('target_frames must be a positive integer')
        if Fraction(str(clip['source_in_s'])) < 0 or Fraction(str(clip['source_out_s'])) <= Fraction(str(clip['source_in_s'])):
            raise ValueError('Invalid source interval')
        if 'output_start_frame' in clip and clip['output_start_frame'] != cursor:
            raise ValueError('Timeline overlap or gap at ' + clip['id'])
        clip['output_start_frame'] = cursor
        cursor += clip['target_frames']
        if 'output_end_frame' in clip and clip['output_end_frame'] != cursor:
            raise ValueError('Incorrect output end at ' + clip['id'])
        clip['output_end_frame'] = cursor
        clip['file'] = str((path.parent / clip['file']).resolve(strict=True))
    if data.get('total_frames', cursor) != cursor:
        raise ValueError('total_frames does not match clips')
    data['total_frames'] = cursor
    data['duration_s'] = float(Fraction(cursor)/fps)
    if data['audio'] is not None:
        data['audio']['file'] = str((path.parent / data['audio']['file']).resolve(strict=True))
        if float(data['audio'].get('source_in_s', 0)) < 0:
            raise ValueError('Audio source_in_s must be nonnegative')
    return data


def verify(file, expected_frames=None, width=None, height=None, fps=None):
    info = probe(file)
    result = run(['ffmpeg', '-v', 'error', '-xerror', '-i', file, '-map', '0:V:0',
                  '-map', '0:a?', '-progress', 'pipe:1', '-nostats', '-f', 'null', '-'])
    counts = re.findall(r'^frame=(\d+)$', result.stdout, re.M)
    if not counts:
        raise ValueError('Decoder returned no frame count')
    frames = int(counts[-1])
    failures = []
    for label, actual, expected in [('frames', frames, expected_frames), ('width', info['width'], width), ('height', info['height'], height)]:
        if expected is not None and actual != expected:
            failures.append(f'{label}: got {actual}, expected {expected}')
    if fps and abs(float(ratio(info['fps'])) - float(ratio(fps))) > .015:
        failures.append(f"fps: got {info['fps']}, expected {fps}")
    if result.stderr.strip():
        failures.append('Decoder emitted errors: ' + result.stderr[-1000:])
    return {'status': 'fail' if failures else 'pass', 'media': info,
            'decoded_frames': frames, 'failures': failures,
            'visual': 'not_checked', 'motion': 'not_checked', 'audio_listening': 'not_checked'}


def render(args):
    data = project(args.project)
    out, work = Path(args.out).resolve(), Path(args.work).resolve()
    if out.exists():
        raise ValueError('Output exists; choose a versioned name')
    out.parent.mkdir(parents=True, exist_ok=True)
    work.mkdir(parents=True, exist_ok=False)
    fps, w, h = str(ratio(data['fps'])), data['width'], data['height']
    parts = []
    for i, clip in enumerate(data['clips']):
        meta = probe(clip['file'])
        start, end = float(clip['source_in_s']), float(clip['source_out_s'])
        if meta['duration_s'] and end > meta['duration_s'] + .05:
            raise ValueError(f"Source interval exceeds {clip['id']} duration")
        target = clip['target_frames'] / float(ratio(fps))
        fit = (f'scale={w}:{h}:force_original_aspect_ratio=increase,crop={w}:{h}'
               if data.get('fit', 'cover') == 'cover' else
               f'scale={w}:{h}:force_original_aspect_ratio=decrease,pad={w}:{h}:(ow-iw)/2:(oh-ih)/2')
        filters = (f'trim=start={start}:end={end},setpts=(PTS-STARTPTS)*{target/(end-start):.12f},'
                   f'fps={fps},{fit},setsar=1,format=yuv420p,'
                   f'tpad=stop_mode=clone:stop_duration={2/float(ratio(fps))},trim=end_frame={clip["target_frames"]},setpts=PTS-STARTPTS')
        part = work/f'part-{i:04d}.mp4'
        run(['ffmpeg', '-v', 'error', '-n', '-i', clip['file'], '-map', '0:V:0', '-an',
             '-vf', filters, '-c:v', 'libx264', '-preset', 'medium', '-crf', '18', '-threads', '2', part])
        check = verify(part, clip['target_frames'], w, h, fps)
        if check['status'] != 'pass':
            raise ValueError(str(check['failures']))
        parts.append(part)
    listing = work/'concat.txt'
    listing.write_text(''.join("file '" + str(p).replace("'", "'\\''") + "'\n" for p in parts))
    joined = work/'joined.mp4'
    run(['ffmpeg', '-v', 'error', '-n', '-f', 'concat', '-safe', '0', '-i', listing,
         '-c', 'copy', '-movflags', '+faststart', joined])
    candidate = work/'final.mp4'
    if data['audio'] is None:
        shutil.copyfile(joined, candidate)
    else:
        a = data['audio']
        af = f"atrim=start={float(a.get('source_in_s', 0))},asetpts=PTS-STARTPTS,apad"
        run(['ffmpeg', '-v', 'error', '-n', '-i', joined, '-i', a['file'],
             '-map', '0:V:0', '-map', '1:a:0', '-af', af, '-c:v', 'copy', '-c:a', 'aac',
             '-b:a', '192k', '-t', data['duration_s'], '-movflags', '+faststart', candidate])
    check = verify(candidate, data['total_frames'], w, h, fps)
    save(work/'timeline.json', data)
    save(work/'technical-check.json', check)
    if check['status'] != 'pass':
        raise ValueError(str(check['failures']))
    with out.open('xb') as dst, candidate.open('rb') as src:
        shutil.copyfileobj(src, dst)
    check['media']['path'] = str(out)
    return check


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    q = sub.add_parser('probe'); q.add_argument('video')
    q = sub.add_parser('sample'); q.add_argument('video'); q.add_argument('--out-dir', required=True)
    q.add_argument('--start-frame', type=int, default=0); q.add_argument('--end-frame', type=int)
    q.add_argument('--step', type=int); q.add_argument('--max-frames', type=int, default=300)
    q = sub.add_parser('timeline'); q.add_argument('project')
    q = sub.add_parser('render'); q.add_argument('project'); q.add_argument('--out', required=True); q.add_argument('--work', required=True)
    q = sub.add_parser('verify'); q.add_argument('video'); q.add_argument('--expected-frames', type=int)
    q.add_argument('--width', type=int); q.add_argument('--height', type=int); q.add_argument('--fps')
    for q in sub.choices.values():
        q.add_argument('--report')
    a = p.parse_args()
    try:
        if not shutil.which('ffmpeg'):
            raise ValueError('FFmpeg is required')
        if a.command == 'probe': result = probe(a.video)
        elif a.command == 'sample': result = sample(a)
        elif a.command == 'timeline': result = project(a.project)
        elif a.command == 'render': result = render(a)
        else: result = verify(a.video, a.expected_frames, a.width, a.height, a.fps)
        if a.report: save(a.report, result)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 1 if result.get('status') == 'fail' else 0
    except (ValueError, OSError, KeyError, TypeError, ZeroDivisionError) as error:
        print(str(error), file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
