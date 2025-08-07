# Optimal Process for Finding Unread Messages

This document outlines the most effective procedure for finding a user's unread messages within the constraints of the available tools and typical user permissions. Direct discovery of all unread messages is not feasible due to API limitations and security models.

## The Problem

A user's permissions are typically scoped to the teams and channels they are members of. Global search tools like `search_all_channels` will often fail with a `403 Forbidden` error because standard users lack the required system-level permissions.

Furthermore, the available tools do not provide a direct way to list all channels a user has joined. Therefore, a targeted, user-guided approach is necessary.

## The Process

Follow these steps rigorously. Do not deviate.

### Step 1: Identify the User's Team

First, you must identify a team to operate within. Most actions are scoped to a team.

1.  **Get User's Teams**: Use the `get_teams_for_user` tool with `user_id: 'me'`.
2.  **Extract `team_id`**: From the result, extract the `id` of the target team. If the user is on multiple teams, you may need to ask them which one to focus on.

### Step 2: Identify a Target Channel (User-Guided)

You cannot reliably get a list of channels the user is a member of. You must ask the user for a channel name.

1.  **Ask the User**: Use `ask_followup_question` to request the name of a channel where they expect unread messages.
2.  **Search for the Channel**: Use the `search_channels` tool with the `team_id` from Step 1 and the `term` provided by the user.
3.  **Extract `channel_id`**: From the result, extract the `id` of the channel.

### Step 3: Check for Unread Messages and Fetch

Once you have a valid `channel_id` for a channel the user is likely a member of, you can check for unread messages.

1.  **Get Unread Count**: Use the `get_channel_unread` tool. If this call results in a `403 Forbidden` error, it means the user is not a member of this channel. Return to Step 2 and ask for a different channel.
2.  **Evaluate Result**: Check the `msg_count` in the response.
    -   If `msg_count > 0`, proceed to the next step.
    -   If `msg_count == 0`, inform the user and ask if they want to check another channel or fetch the latest messages regardless.
3.  **Fetch Posts**: If there are unread messages, use the `get_posts_for_channel` tool to retrieve them.

This iterative, user-guided process is the only reliable method given the current constraints.
