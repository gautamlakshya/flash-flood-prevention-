# Indian SMS & TRAI DLT Compliance Guide

This document outlines the regulatory and architectural requirements for integrating SMS emergency flood notifications in India within the **Chungthang–Teesta Early Warning System (FFEWS)**.

---

## 1. Regulatory Framework: TRAI TCCCPR (2018)

In India, all SMS communications transmitted over telecom networks are regulated by the **Telecom Regulatory Authority of India (TRAI)** under the:

> **Telecom Commercial Communications Customer Preference Regulations, 2018 (TCCCPR, 2018)**

Under these regulations, bulk SMS and emergency alert dissemination must operate through a **Distributed Ledger Technology (DLT)** portal operated by Indian telecom access providers (Airtel, Reliance Jio, Vodafone Idea, or BSNL / Vilpower).

Unregistered SMS messages or unauthorized header names are strictly rejected by telecom firewall filters at the operator level.

---

## 2. Mandatory Compliance Requirements for Production Deployment

Before any live SMS can be transmitted from this early warning prototype:

### Step 1: Principal Entity (PE) Registration
- The deploying department or agency (e.g. **Sikkim State Disaster Management Authority - SSDMA**, District Disaster Management Authority Mangan, or National Disaster Management Authority - NDMA) must register as a **Principal Entity (Government / Enterprise)** on a DLT portal.
- Required documents: Government authorization letter, PAN card, TAN, proof of office address, and authorized signatory identification.
- Output: A unique **DLT Principal Entity ID (PE ID)** (19-digit identifier).

### Step 2: Header (Sender ID) Registration
- For emergency and disaster warnings, headers must be registered under the **Transactional / Service** category.
- Header Format: Exactly **6 uppercase alphabetic characters** representing the sender agency.
- Example registered headers for Chungthang Teesta warning:
  - `SKMFLW` (Sikkim Flood Warning)
  - `SSDMAF` (Sikkim SDMA Flood)
  - `DMNGAN` (Disaster Management Mangan)

### Step 3: Content Template Registration
- Every message template must be submitted and approved on the DLT portal before transmission.
- Templates use fixed text with dynamic variable placeholders: `{#var#}`.
- Maximum variable length and character count must be adhered to (160 characters per standard GSM 7-bit SMS segment, or Unicode for regional languages like Nepali/Hindi).

#### Approved Disaster Warning Template Example:
```text
EMERGENCY FLOOD WARNING: {#var#} river discharge has reached {#var#} m3/s exceeding critical threshold. Evacuate immediately to {#var#}. - Sikkim SDMA
```

#### Approved All-Clear Template Example:
```text
FLOOD ALERT RESOLVED: Water levels at {#var#} have receded to {#var#} m3/s. River conditions are returning to normal. - Sikkim SDMA
```

---

## 3. Consent & Emergency Exception Guidelines

- **General Commercial Communications:** Require explicit, documented consumer opt-in consent recorded on the DLT consent registry.
- **Disaster & Life-Safety Alerts (Section 19 Emergency Exemption):**
  - Emergency alerts issued by recognized State and District Disaster Management Authorities under the **Disaster Management Act, 2005** are exempt from commercial opt-out restrictions (Do Not Disturb / DND filters).
  - However, to transmit without DND filtering, the SMS gateway provider (e.g. CDAC, BSNL, NIC, Tanla, Gupshup, ValueFirst) must be provisioned with an **NDMA / SDMA Priority Route** authorized by the Ministry of Communications.

---

## 4. Architecture in the Chungthang Prototype

The prototype implements an extensible, plug-and-play channel interface:
`backend/app/alerts/sms.py -> SMSNotificationChannel`

### Architectural Guarantees:
1. **Honest "NOT CONFIGURED" State:**
   - The system **never fabricates** fake SMS dispatches, simulated phone numbers, or false delivery receipts.
   - If `SMS_ENABLED=false` or DLT credentials (`SMS_ENTITY_ID`, `SMS_SENDER_ID`) are absent, the channel reports `NOT CONFIGURED` to the UI and API.
2. **Zero Recipient Leaks:**
   - Phone numbers and subscriber identifiers are never printed to frontend logs or exposed via public API endpoints.
   - All audit logs mask recipient identifiers (e.g. `+91-XXXXX-98765`).
3. **Pluggable Gateway Provider:**
   - When an approved gateway (e.g. CDAC Emergency Messaging Service or NIC SMS Gateway) is procured, only the `dispatch()` method in `backend/app/alerts/sms.py` requires gateway API endpoint binding. The core alert engine, hysteresis, and evaluation rules remain unchanged.

---

## 5. Environment Variables for SMS Configuration

When deploying with verified credentials, configure the following backend variables:

```bash
# Enable SMS Channel
SMS_ENABLED=true

# Gateway Configuration
SMS_PROVIDER=cdac_ems # or nic, tanla, gupshup
SMS_GATEWAY_URL=https://api.sms-gateway.gov.in/v1/send
SMS_API_KEY=your_secured_gateway_key

# TRAI DLT Identifiers
SMS_ENTITY_ID=1101234567890123456  # 19-digit DLT PE ID
SMS_SENDER_ID=SKMFLW               # 6-character approved header
```
