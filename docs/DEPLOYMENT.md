# Streamlit Community Cloud Deployment Guide

This guide will help you deploy the Financial Advisor app to Streamlit Community Cloud.

## Prerequisites

- Your repository is already pushed to GitHub at `https://github.com/abhorkarpet/financialadvisor`
- A GitHub account
- A Streamlit Community Cloud account (free)

## Deployment Steps

### 1. Sign up for Streamlit Community Cloud

1. Go to [share.streamlit.io](https://share.streamlit.io)
2. Sign in with your GitHub account
3. Authorize Streamlit to access your GitHub repositories

### 2. Deploy Your App

1. Click **"New app"** button
2. Select your repository: `abhorkarpet/financialadvisor`
3. Select the branch: `main`
4. Set the **Main file path**: `fin_advisor.py`
5. (Optional) Give your app a custom URL: e.g., `financial-advisor`
6. Click **"Deploy"**

### 3. Wait for Deployment

- Streamlit will automatically:
  - Install dependencies from `requirements.txt`
  - Build and deploy your app
  - Provide you with a public URL (e.g., `https://financial-advisor.streamlit.app`)

### 4. Automatic Updates

- Every time you push to the `main` branch, Streamlit will automatically redeploy your app
- You can also manually trigger redeployments from the Streamlit dashboard

## Configuration Files

The repository includes:
- ✅ `requirements.txt` - All Python dependencies
- ✅ `.streamlit/config.toml` - Streamlit configuration (theme, server settings)

## Troubleshooting

### Common Issues

1. **Import Errors**: Make sure all dependencies are in `requirements.txt`
2. **App Not Loading**: Check the logs in the Streamlit dashboard
3. **Slow Performance**: Consider optimizing data loading or using caching

### Viewing Logs

1. Go to your app's dashboard on share.streamlit.io
2. Click on your app
3. View logs in the "Logs" section

## App URL

Once deployed, your app will be available at:
`https://[your-app-name].streamlit.app`

## Additional Resources

- [Streamlit Community Cloud Documentation](https://docs.streamlit.io/streamlit-community-cloud)
- [Streamlit Deployment Guide](https://docs.streamlit.io/streamlit-community-cloud/deploy-your-app)

