import sys
import os

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from edi_parser import parse_segments, detect_transaction_type, extract_snip_errors

with open('data/synthetic_edi/837P_with_errors.edi') as f:
    edi = f.read()

segments = parse_segments(edi)
tx_type = detect_transaction_type(segments)
issues = extract_snip_errors(segments, tx_type)

print(f'Transaction: {tx_type}')
print(f'Segments found: {len(segments)}')
print(f'Pre-validation issues: {len(issues)}')
for i in issues:
    print(f'  [SNIP {i["snip"]}] {i["severity"]} - {i["message"]}')