import json
import os
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

ROOT = Path(os.environ.get('SITE_DIR', 'site'))
PAGES = ['index.html','about.html','services.html','projects.html','contact.html']

class DocumentParser(HTMLParser):
    def __init__(self):
        super().__init__()
        self.links=[];self.assets=[];self.tags=set();self.has_title=False;self.has_lang=False
    def handle_starttag(self, tag, attrs):
        a=dict(attrs);self.tags.add(tag)
        if tag=='html' and a.get('lang'):self.has_lang=True
        if tag=='a' and a.get('href'):self.links.append(a['href'])
        if tag=='link' and a.get('href'):self.assets.append(a['href'])
        if tag=='script' and a.get('src'):self.assets.append(a['src'])
        if tag=='title':self.has_title=True

def test_all_required_pages_exist():
    for page in PAGES:assert (ROOT/page).is_file(),f'Missing required page: {page}'

def test_pages_structure_links_assets():
    for page in PAGES:
        doc=DocumentParser();text=(ROOT/page).read_text(encoding='utf-8');doc.feed(text)
        assert '<!doctype html>' in text.lower(),f'{page}: missing doctype'
        assert {'html','head','body','main','nav'}.issubset(doc.tags),page
        assert doc.has_title and doc.has_lang,page
        for href in doc.links+doc.assets:
            if href.startswith(('#','//','mailto:','tel:')):continue
            parsed=urlsplit(href)
            if parsed.scheme:continue
            target=(ROOT/parsed.path.lstrip('/')).resolve()
            assert target.is_relative_to(ROOT.resolve()),f'{page}: unsafe link {href}'
            assert target.is_file(),f'{page}: broken link/asset {href}'

def test_real_project5_js_feature():
    html=(ROOT/'contact.html').read_text();js=(ROOT/'script.js').read_text()
    assert 'id="contact-form"' in html and 'id="form-status"' in html
    assert 'addEventListener' in js and "mailto:" in js and 'preventDefault' in js
    assert 'menu-toggle' in (ROOT/'index.html').read_text()

def test_release_identity():
    path=ROOT/'release.json'
    assert path.is_file(),'Run python scripts/build.py before tests'
    obj=json.loads(path.read_text())
    assert isinstance(obj.get('release_id'),str) and len(obj['release_id'])>=7
