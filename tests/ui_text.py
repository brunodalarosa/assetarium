"""Shared source/native checks for misdecoded UI text; never rewrite asset data."""
import re


# Typical UTF-8 bytes decoded as Windows-1252, plus replacement/C1 characters.
# Correct accented text and symbols (including asset names) remain valid.
MOJIBAKE = re.compile(
    r'[\u00c2\u00c3][\u0080-\u00bf]|\u00e2[\u0080-\u00bf\u2010-\u203a\u20ac]'
    r'|\u00ef\u00bf\u00bd|\u00f0\u0178|[\u0080-\u009f\ufffd]')


BROWSER_TEXT = """(()=>{
  const entries=[];
  const walker=document.createTreeWalker(document.body,NodeFilter.SHOW_TEXT);
  while(walker.nextNode()){
    const node=walker.currentNode;
    if(!node.parentElement?.closest('script,style')&&node.textContent.trim())
      entries.push({where:node.parentElement?.id||node.parentElement?.tagName,text:node.textContent});
  }
  for(const element of document.body.querySelectorAll('*')){
    for(const name of ['title','alt','placeholder','aria-label','aria-description','aria-valuetext']){
      const text=element.getAttribute(name);
      if(text)entries.push({where:(element.id||element.tagName)+'@'+name,text});
    }
  }
  return entries;
})()"""


def assert_ui_text(window, label, report):
    entries = window.evaluate_js(BROWSER_TEXT)
    bad = [item for item in entries if MOJIBAKE.search(item['text'])]
    assert not bad, {'screen': label, 'corrupted_ui_text': bad}
    report.setdefault('text_encoding_checks', []).append({'screen': label, 'strings_checked': len(entries)})
