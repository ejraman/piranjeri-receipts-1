Updated v4

Changes:
- Replaced 'Draft No.' with 'Bank Transfer'
- Cash / Cheque / Bank Transfer now behave as follows:
  - cash: strikes Cheque and Bank Transfer
  - cheque: strikes Cash and Bank Transfer, prints Cheque No.
  - bank_transfer: strikes Cash and Cheque, prints Date of credit in DD MM YYYY
