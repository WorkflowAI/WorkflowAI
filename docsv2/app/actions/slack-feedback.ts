'use server';

import type { Feedback } from '@/components/rate';

export async function sendFeedbackToSlack(url: string, feedback: Feedback) {
  // Get the Slack webhook URL from environment variable
  const slackWebhookUrl = process.env.SLACK_WEBHOOK_URL;
  
  if (!slackWebhookUrl) {
    console.error('SLACK_WEBHOOK_URL environment variable is not set');
    return;
  }

  // Prepare the message for Slack
  const emoji = feedback.opinion === 'good' ? ':thumbsup:' : ':thumbsdown:';
  const color = feedback.opinion === 'good' ? '#36a64f' : '#ff6b6b';
  
  const slackMessage = {
    attachments: [
      {
        color: color,
        title: `Documentation Feedback ${emoji}`,
        fields: [
          {
            title: 'Page',
            value: url,
            short: false
          },
          {
            title: 'Opinion',
            value: feedback.opinion.charAt(0).toUpperCase() + feedback.opinion.slice(1),
            short: true
          },
          {
            title: 'Timestamp',
            value: new Date().toISOString(),
            short: true
          }
        ]
      }
    ]
  };

  // Add message if provided
  if (feedback.message.trim()) {
    slackMessage.attachments[0].fields.push({
      title: 'Message',
      value: feedback.message,
      short: false
    });
  }

  try {
    const response = await fetch(slackWebhookUrl, {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify(slackMessage),
    });

    if (!response.ok) {
      console.error('Failed to send feedback to Slack:', response.status, response.statusText);
    }
  } catch (error) {
    console.error('Error sending feedback to Slack:', error);
  }
} 