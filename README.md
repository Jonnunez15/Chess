# Chess Analytics Mobile PWA

A mobile-first installable web app for Chess.com matchup analytics.

## Features
- Pulls all public monthly Chess.com game archives
- Top 10 most-played opponents
- Career W-L-D and score percentage
- Average opponent rating
- White/Black breakdown
- Head-to-head explorer
- Rapid/Blitz/Bullet records
- PWA manifest + service worker for Add to Home Screen

## Browser-only deployment
1. Create a GitHub repository using the files in this folder.
2. In Render, choose **New → Web Service** and connect the GitHub repo.
3. Render reads `render.yaml`; approve the deployment.
4. Open the resulting HTTPS URL on your phone.
5. iPhone: Safari → Share → Add to Home Screen. Android: Chrome → Install app / Add to Home screen.

No Chess.com password is required; the app uses public game data only.
