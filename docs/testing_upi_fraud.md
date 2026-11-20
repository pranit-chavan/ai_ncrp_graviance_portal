# Manual test scenario: UPI payment fraud

Use this fictional scenario to exercise the victim-facing complaint workflow. It contains no real personal or banking information. Do not submit a real complaint while testing.

## Test data

- Main category to expect: Online Financial Fraud
- Expected sub-category: UPI Related Frauds
- Test name: Ananya Test
- Test contact: Use a non-real test value only if the form requires one.
- Incident date: 15 October 2026 (fictional)
- Approximate loss: INR 4,500
- Payment method: UPI
- Fictional transaction reference: TEST-UPI-20261015-001
- Fictional recipient handle: demo-seller@example

## Guided intake answers

Start a complaint and begin guided intake in English. Give the first statement below; answer the assistant's follow-up questions with the matching details. If it asks for a detail not covered here, answer “I don’t know” rather than inventing one.

**Initial statement:**

> I paid a seller through UPI for a phone, but the seller stopped responding and I did not receive the phone.

**Details to provide when asked:**

- I found the seller in a fictional online marketplace listing.
- I paid INR 4,500 on 15 October 2026 using a UPI app.
- The payment went to the fictional handle `demo-seller@example`.
- The transaction reference shown in the sample receipt is `TEST-UPI-20261015-001`.
- The seller promised delivery in three days, then stopped replying.
- I contacted the seller once more; no refund has been received.
- I do not know the seller's real name or location.

Finish intake, review the generated narrative for accuracy, and continue to evidence review.

## Evidence/OCR check

Use the included fictional [UPI receipt screenshot](../test_evidence_upi_receipt.png), which displays only the amount, date, UPI handle, and test transaction reference above. Do not upload a genuine receipt, account number, UPI PIN, OTP, phone number, or other personal data.

1. Upload the sample evidence.
2. Select **Extract text and review evidence**.
3. Confirm the extracted amount, date, payment method, recipient, and reference against the fictional data above.
4. If the OCR reading conflicts with the complaint, verify that the UI asks which value is correct; choose the test receipt value only for this fictional case.
5. Confirm evidence details and continue.

## Classification and output checks

1. Run the classifier and note its predicted sub-category and confidence. The intended result is **UPI Related Frauds** under **Online Financial Fraud**. Model output may vary; record a different prediction as a classification error for review rather than editing the complaint to force the expected answer.
2. Check that the summary uses only the facts supplied and does not invent a date, amount, or suspect identity.
3. Review the preliminary legal mapping and its verification disclaimer.
4. Complete the remaining form fields with fictional/test values, review the preview, and generate the local complaint-record PDF.
5. Verify that the PDF is described as a preliminary local record, not an official NCRP filing or acknowledgement.
6. Record the predicted label, confidence, OCR errors, summary issues, and PDF path below.

## Result log

- Date/time tested:
- Predicted main category:
- Predicted sub-category:
- Confidence (if shown):
- OCR correct after review? Yes / No / Not tested
- Summary accurate? Yes / No
- PDF generated and disclaimer present? Yes / No
- Notes:
