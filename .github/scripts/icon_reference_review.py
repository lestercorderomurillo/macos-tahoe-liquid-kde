"""Register original Mac captures and compare icon paint at actual capture size.

This produces local review artifacts, not installable assets or release evidence.
Original screenshots stay outside version control. Never infer an appearance
from its filename alone: inspect the selected control in the complete frame.
"""
from pathlib import Path
import argparse
import hashlib
import importlib.util
import io
import json
import sys
from statistics import median
import math

from PIL import Image, ImageCms, ImageDraw, ImageFont


def load_renderer(repo):
    spec = importlib.util.spec_from_file_location('review_materials', repo / 'src/scripts/icon_materials.py')
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


def luminance(p):
    return sum((v / 3294.6 if v <= 10.31475 else ((v / 255 + .055) / 1.055) ** 2.4) * w
               for v, w in zip(p[:3], (.2126, .7152, .0722)))


def sample(im, box):
    w, h = im.size
    patch = im.crop(tuple(round(v * (w if i % 2 == 0 else h)) for i, v in enumerate(box)))
    return tuple(round(median(p[c] for p in patch.getdata())) for c in range(3))


def contrast(a, b):
    low, high = sorted((luminance(a), luminance(b)))
    return (high + .05) / (low + .05)


def field(im):
    """Approximate the obscured Dock backing from the four clear crop corners.

    This is marked as an estimate: it cannot recover macOS live refraction.
    """
    points = [sample(im, box) for box in ((0, 0, .04, .04), (.96, 0, 1, .04),
                                        (0, .96, .04, 1), (.96, .96, 1, 1))]
    corners = Image.new('RGB', (2, 2)); corners.putdata(points)
    return corners.resize(im.size, Image.Resampling.BILINEAR).convert('RGBA')


REGIONS = {
    'plate_top': (.13, .16, .22, .25),
    'plate_bottom': (.13, .72, .22, .81),
    'face': (.74, .48, .82, .60),
}


def metrics(im, name):
    if name == 'view-app-grid':
        return {key: sample(im, rect) for key, rect in {
            'search': (.32,.27,.65,.31), 'tile_orange': (.25,.49,.31,.53),
            'tile_green': (.66,.49,.72,.53), 'tile_gray': (.66,.69,.72,.73),
            'plate_top': (.14,.14,.21,.21), 'plate_bottom': (.14,.79,.21,.86),
        }.items()}
    values = {key: sample(im, rect) for key, rect in REGIONS.items()}
    # A small ROI search accommodates genuine differences between the two
    # original drawings, without moving/repainting the reference eye.
    w, h = im.size
    eye = im.crop((round(w*.24), round(h*.25), round(w*.40), round(h*.46)))
    bg = sample(im, (.17, .29, .23, .43))
    ranked = sorted(eye.getdata(), key=lambda p: abs(luminance(p)-luminance(bg)))
    selected = ranked[-max(1, len(ranked)//12):]
    eye_rgb = tuple(round(median(p[c] for p in selected)) for c in range(3))
    values.update(eye=eye_rgb, eye_background=bg,
                  eye_contrast=round(contrast(eye_rgb,bg),3),
                  eye_polarity='lighter' if luminance(eye_rgb)>luminance(bg) else 'darker')
    face = sample(im, (.79,.35,.83,.43))
    right_roi = im.crop((round(w*.59), round(h*.28), round(w*.76), round(h*.46)))
    darkest = sorted(right_roi.getdata(), key=luminance)
    darkest = darkest[:max(1,len(darkest)//12)]
    right = tuple(round(median(p[c] for p in darkest)) for c in range(3))
    values.update(right_eye=right, right_eye_background=face,
                  right_eye_contrast=round(contrast(right,face),3),
                  right_eye_polarity='lighter' if luminance(right)>luminance(face) else 'darker')
    return values


def oklab(rgb):
    r, g, b = [v/3294.6 if v <= 10.31475 else ((v/255+.055)/1.055)**2.4 for v in rgb]
    l = (.4122214708*r+.5363325363*g+.0514459929*b)**(1/3)
    m = (.2119034982*r+.6806995451*g+.1073969566*b)**(1/3)
    s = (.0883024619*r+.2817188376*g+.6299787005*b)**(1/3)
    return (.2104542553*l+.793617785*m-.0040720468*s,
            1.9779984951*l-2.428592205*m+.4505937099*s,
            .0259040371*l+.7827717662*m-.808675766*s)


def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--repo',type=Path,required=True)
    p.add_argument('--reference',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--output',type=Path,required=True)
    p.add_argument('--baseline',type=Path,help='Previous output from these same registered references')
    a=p.parse_args();a.output.mkdir(parents=True,exist_ok=True)
    renderer=load_renderer(a.repo)
    manifest=json.loads((Path(__file__).resolve().parents[1]/'icon-reference-frames.json').read_text())
    records=manifest['frames']
    font=ImageFont.truetype('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf',15)
    # Native crops are saved separately. The board enlarges with nearest-neighbor
    # only, to expose source pixels rather than manufacture apparent detail.
    board=Image.new('RGB',(1150,len(records)*260+50),'#e7e8ea');d=ImageDraw.Draw(board)
    d.text((230,10),'Finder: Mac / candidate       Apps: Mac / candidate (2x pixels)',font=font,fill='black')
    report=[]
    for row,record in enumerate(records):
        path=a.reference/(record['name']+'.png');raw=path.read_bytes();im=Image.open(io.BytesIO(raw))
        if hashlib.sha256(raw).hexdigest() != record['sha256'] or list(im.size) != record['dimensions']:
            raise ValueError(f"Reference changed: {path}; inspect and register it before comparing")
        profile=im.info.get('icc_profile')
        if profile:
            im=ImageCms.profileToProfile(im,ImageCms.ImageCmsProfile(io.BytesIO(profile)),
                                        ImageCms.createProfile('sRGB'),outputMode='RGBA')
        else:im=im.convert('RGBA')
        entry=record|{'sha256':hashlib.sha256(raw).hexdigest(),'dimensions':list(im.size),
                      'icc_sha256':hashlib.sha256(profile).hexdigest() if profile else None,
                      'backing':'Estimated from crop corners, not original unobscured wallpaper',
                      'icons':{}}
        d.text((8,row*260+70),record['name'],font=font,fill='black')
        for index,name in enumerate(('system-file-manager','view-app-grid')):
            x,y=record['origin'];x+=record['step']*index;n=record['size']
            crop=im.crop((x,y,x+n,y+n));src=a.source/'apps/scalable'/(name+'.svg')
            prepared=renderer.prepare_source(src,512)
            generated=renderer.render(prepared,record['variant'],record['tint']).resize((256,256),Image.Resampling.LANCZOS).resize((n,n),Image.Resampling.LANCZOS)
            result=Image.alpha_composite(field(crop),generated)
            pair={'reference':crop,'candidate':result}
            for col,(kind,part) in enumerate(pair.items()):
                part.save(a.output/(record['name']+'-'+name+'-'+kind+'.png'))
                zoom=part.resize((n*2,n*2),Image.Resampling.NEAREST)
                board.paste(zoom,(230+index*440+col*216,row*260+45))
            entry['icons'][name]={'crop':[x,y,x+n,y+n],
                                  'reference':metrics(crop,name),'candidate':metrics(result,name),
                                  'artwork_sha256':hashlib.sha256(src.read_bytes()).hexdigest()}
            measures=entry['icons'][name]
            # Compare paint patches, not whole silhouettes with different drawings.
            measures['paint_delta_ok']={}
            for key, rgb in measures['reference'].items():
                if isinstance(rgb,tuple):
                    ref=oklab(rgb)
                    got=oklab(measures['candidate'][key])
                    measures['paint_delta_ok'][key]=round(100*math.dist(ref,got),3)
            annotated=crop.copy();mark=ImageDraw.Draw(annotated)
            if name=='system-file-manager':
                for rect in list(REGIONS.values())+[(.24,.25,.40,.46),(.59,.28,.76,.46)]:
                    mark.rectangle(tuple(round(v*n) for v in rect),outline='magenta',width=1)
                annotated.resize((n*4,n*4),Image.Resampling.NEAREST).save(a.output/(record['name']+'-sampling.png'))
        selector=im.crop(record['selector_crop'])
        selector.save(a.output/(record['name']+'-selected-mode.png'))
        report.append(entry)
    board.save(a.output/'comparison.png')
    (a.output/'measurements.json').write_text(json.dumps({'renderer_sha256':hashlib.sha256((a.repo/'src/scripts/icon_materials.py').read_bytes()).hexdigest(),'frames':report},indent=2)+'\n')
    if a.baseline:
        previous=json.loads((a.baseline/'measurements.json').read_text())['frames']
        previous={r['name']:r for r in previous}
        summary=['| Capture | Finder paint error before / candidate | Left eye: Mac / before / candidate |',
                 '| --- | --- | --- |']
        # Equal physical pixel scale, fixed crop, no stretching or image warping.
        comparison=Image.new('RGB',(1140,40+len(records)*230),'#e7e8ea')
        pen=ImageDraw.Draw(comparison)
        pen.text((180,8),'Finder: Mac | before | candidate       Apps: Mac | before | candidate',font=font,fill='black')
        for row,current in enumerate(report):
            before=previous[current['name']]
            if before['sha256']!=current['sha256'] or before['tint']!=current['tint']:
                raise ValueError('Baseline reference/tint changed; regenerate the baseline')
            n=current['size'];name=current['name']
            pen.text((5,60+row*230),name.replace('native-',''),font=font,fill='black')
            for index,icon in enumerate(('system-file-manager','view-app-grid')):
                if before['icons'][icon]['artwork_sha256']!=current['icons'][icon]['artwork_sha256']:
                    raise ValueError('Source artwork changed; this is not a paint-only comparison')
                for col,(directory,kind) in enumerate(((a.output,'reference'),(a.baseline,'candidate'),(a.output,'candidate'))):
                    part=Image.open(directory/(name+'-'+icon+'-'+kind+'.png'))
                    # Native crops at 1x: the independent zoom board provides 2x.
                    comparison.paste(part.resize((n*2,n*2),Image.Resampling.NEAREST),
                                     (180+index*480+col*160,40+row*230))
            old=before['icons']['system-file-manager'];new=current['icons']['system-file-manager']
            errors=[sum(v['paint_delta_ok'][k] for k in REGIONS)/len(REGIONS) for v in (old,new)]
            polarities=[v['eye_polarity'] for v in (new['reference'],old['candidate'],new['candidate'])]
            summary.append(f"| {name} | {errors[0]:.1f} / {errors[1]:.1f} | {' / '.join(polarities)} |")
        # Native PNG crops need wider slots; red/blue video crops fit this panel.
        panel=Image.new('RGB',(1140,960),'#e7e8ea')
        panel.paste(comparison.crop((0,0,1140,40)),(0,0))
        panel.paste(comparison.crop((0,40+6*230,1140,40+10*230)),(0,40))
        panel.save(a.output/'red-blue-before-after.png')
        (a.output/'comparison.md').write_text('\n'.join(summary)+'\n\nError: 100 × Euclidean OKLab distance, mean of three Finder paint patches. '
            'This is a diagnostic, not a whole-icon similarity score or an approval gate.\n')
    appearances=[('light',(0,123,252)),('dark',(0,123,252)),
                 ('clear-light',(0,123,252)),('clear-dark',(0,123,252)),
                 ('tinted-light',(0,123,252)),('tinted-dark',(0,123,252)),
                 ('tinted-light',(252,49,50)),('tinted-dark',(252,49,50))]
    gallery=Image.new('RGB',(1200,850),'#73929e');pen=ImageDraw.Draw(gallery)
    geometry=[]
    for col,entry in enumerate(manifest['dock_artwork']):
        path=a.source/('places' if entry['name'].startswith('user-trash') else 'apps')/'scalable'/entry['name']
        if hashlib.sha256(path.read_bytes()).hexdigest()!=entry['source_sha256']:
            raise ValueError(f'Original Dock artwork changed: {path}')
        prepared=renderer.prepare_source(path,256)
        original=prepared[0].getchannel('A')
        pen.text((160+col*80,10),entry['name'][:10],font=font,fill='black')
        for row,(variant,tint) in enumerate(appearances):
            output=renderer.render(prepared,variant,tint)
            coverage=output.getchannel('A')
            if coverage.getbbox()!=original.getbbox() or any(a>0 and b==0 for a,b in zip(coverage.getdata(),original.getdata())):
                raise ValueError(f'Geometry changed: {path} {variant}')
            small=output.resize((72,72),Image.Resampling.LANCZOS)
            gallery.paste(small,(160+col*80,50+row*100),small)
            if col==0:
                pen.text((5,75+row*100),variant+(' red' if row>5 else ''),font=font,fill='black')
        geometry.append(entry)
    gallery.save(a.output/'dock-all-modes.png')
    (a.output/'geometry.json').write_text(json.dumps({'artwork':geometry,'appearances':appearances,
        'claim':'Same bounds, no coverage outside the original silhouette; color/opacity may change'},indent=2)+'\n')
    print(a.output/'comparison.png')

if __name__=='__main__':main()
