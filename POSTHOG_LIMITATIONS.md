# PostHog Analytics in Streamlit - What Works & Limitations

## ✅ What DOES Work

### 1. Event Tracking ✅
- All custom events are tracked perfectly
- `onboarding_completed`, `pdf_generation_success`, `monte_carlo_run`, etc.
- Events appear in PostHog → Activity → Events

### 2. Session Analytics ✅ (NOW FIXED)
- **Session ID** - Unique ID per user session
- **Session Duration** - How long users spend in the app
- **Events per Session** - Number of actions per visit
- **Session Start/End Timestamps**

Every event now includes:
- `$session_id` - Groups events into sessions
- `$session_start_timestamp` - When the session began

**Where to see it:**
- PostHog → Insights → Create new insight
- Filter by "Session ID" to see session-based metrics
- Use "Session Duration" in analytics queries

### 3. User Identification ✅
- Anonymous user IDs (UUID-based)
- User properties and attributes
- User journey tracking across sessions

### 4. Page Tracking ✅
- Page views with URLs and screen names
- Navigation flow analytics
- Time spent per page (via events)

---

## ❌ What DOESN'T Work (Streamlit Limitations)

### 1. Session Replay ❌ (NOT POSSIBLE)

**Why it doesn't work:**
- Session replay requires **PostHog's JavaScript SDK** running in the browser
- Streamlit apps are **server-side Python** applications
- The browser only receives rendered HTML, not interactive JavaScript
- `st.components.html()` runs in isolated iframes with limited access

**What session replay would have shown:**
- Video-like playback of user interactions
- Mouse movements, clicks, scrolls
- Form interactions
- UI element inspection

**Alternative:** Use the session analytics (events + session properties) to understand:
- What pages users visited
- What actions they took (events)
- How long they spent (session duration)
- Where they dropped off (funnel analysis)

### 2. Autocapture ❌ (Limited in Streamlit)

**Why it doesn't work:**
- Autocapture requires JavaScript to automatically track clicks, form submissions, etc.
- Streamlit doesn't expose DOM events to Python

**Solution:** We manually track all important interactions via `track_event()` calls

### 3. Real-time Session Monitoring ❌

**Why it doesn't work:**
- Real-time session monitoring in PostHog relies on the JavaScript SDK
- Python SDK sends events server-side, not real-time browser activity

---

## 🎯 What You CAN Do with PostHog + Streamlit

Even without session replay, you can still get powerful insights:

### 1. Session-Based Analytics
```python
# Every event includes session properties automatically
track_event('onboarding_completed', {'num_accounts': 5})

# PostHog sees:
# - Event: onboarding_completed
# - Session ID: abc-123-def
# - User ID: user-456
# - Timestamp: ...
```

**Queries you can run:**
- Average session duration
- Events per session
- Sessions per user
- Session conversion rates

### 2. User Journeys
Track the sequence of actions users take:
- Splash → Consent → Onboarding Step 1 → Step 2 → Results → PDF
- Identify where users drop off
- See common paths through the app

### 3. Feature Usage Tracking
```python
track_pdf_generation(success=True)
track_monte_carlo_run(num_simulations=1000, volatility=15.0)
track_statement_upload(success=True, num_statements=3, num_accounts=5)
```

See which features are most popular.

### 4. Error Tracking
```python
track_error('pdf_generation_error', error_message, context)
```

Identify bugs and failure patterns.

### 5. Funnel Analysis
- What % of users complete onboarding?
- How many generate PDFs?
- What's the conversion from splash → completed analysis?

---

## 📊 How to View Session Analytics in PostHog

1. **Go to Insights → New Insight**
2. **Select "Trends" or "Funnels"**
3. **Group by** → Choose "$session_id"
4. **Filter by** → Choose specific events or pages

**Example Queries:**

**Average Events per Session:**
```
Events: Any event
Group by: Session ID
Aggregate: Average count
```

**Session Duration:**
```
Events: session_started and session_ended
Calculate: Time between events
Group by: Session ID
```

**User Journey (Funnel):**
```
Step 1: analytics_consent_accepted
Step 2: onboarding_step1_completed
Step 3: onboarding_step2_completed
Step 4: onboarding_completed
```

This shows drop-off at each step!

---

## 🔄 Testing Session Analytics

1. **Reset analytics session:**
   - Advanced Settings → Analytics & Privacy → Reset Analytics Session

2. **Enable debug mode:**
   ```bash
   # In .env
   ANALYTICS_DEBUG=true
   ```

3. **Run the app and watch terminal:**
   ```bash
   streamlit run fin_advisor.py
   ```

4. **You should see:**
   ```
   [Analytics] Tracking event: onboarding_step1_completed
   [Analytics]   User ID: abc-123-def
   [Analytics]   Session ID: session-xyz-789
   [Analytics]   Properties: {..., '$session_id': 'session-xyz-789', ...}
   ```

5. **In PostHog:**
   - Go to Activity → Events
   - Click on any event
   - Look for `$session_id` property
   - All events in same session will have the same session ID!

---

## Summary

| Feature | Works? | How to Access |
|---------|--------|---------------|
| Event Tracking | ✅ Yes | PostHog → Events |
| Session Analytics | ✅ Yes | PostHog → Insights (filter by $session_id) |
| User Identification | ✅ Yes | PostHog → Persons |
| Page Tracking | ✅ Yes | Check event properties ($current_url, page) |
| Session Replay | ❌ No | Not possible in Streamlit |
| Autocapture | ❌ Limited | Use manual track_event() instead |

**Bottom line:** You get comprehensive analytics, just not the visual session replay feature. The session-based analytics (duration, events, funnels) work perfectly!
