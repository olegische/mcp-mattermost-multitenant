# How to Work With Unread Messages

This document provides the definitive, verified process for identifying and managing unread messages and threads using the available MCP tools. Any deviation from this process is incorrect.

## The Problem

A user's permissions are typically scoped to the teams and channels they are members of. Global search tools like `search_all_channels` will often fail with a `403 Forbidden` error because standard users lack the required system-level permissions. A systematic, multi-step process is required to gather a complete picture of a user's unread messages.

## The Process

The overall workflow is as follows:

1.  **Identify User and Teams**: Get the user's ID and the teams they belong to.
2.  **Check Channel Unreads**: For each team, get the user's channels and check each one for unread messages.
3.  **Check Thread Unreads**: For each team, get the user's followed threads to check for unread replies and mentions.
4.  **Mark as Read**: Use the appropriate tool to mark threads as read.

---

### Step 1: Identify User and Teams

First, establish the context of the user and their teams.

-   **Get User ID**: Start by getting the current user's ID.
    ```
    tool: get_user(user_id="me")
    ```
-   **Get Teams**: Get the list of teams the user is a member of.
    ```
    tool: get_teams_for_user(user_id=<user_id>)
    ```
-   **Get Team Unread Summary**: For a high-level overview for a specific team, use `get_team_unread`.
    ```
    tool: get_team_unread(user_id=<user_id>, team_id=<team_id>)
    ```
    **CRITICAL NOTE**: The summary from `get_team_unread` is **unreliable** for thread counts. Do not use it for anything other than a general idea of channel messages and mentions.

### Step 2: Check Channel Unreads

This is the process for finding unread messages in all channel types, including public channels, private channels, direct messages (DMs), and group messages (GMs).

-   **Get All User Channels**: Fetch the complete list of channels the user is a member of across all teams.
    ```
    tool: get_channels_for_user(user_id=<user_id>)
    ```
-   **Filter and Check**: Iterate through the full list of channels. For each channel, take its `id` and use it to call the `get_channel_unread` tool. You can filter this list by `team_id` or by channel `type` (`'O'`, `'P'`, `'D'`, `'G'`) as needed.
    ```
    tool: get_channel_unread(user_id=<user_id>, channel_id=<channel_id>)
    ```
-   **Aggregate and Report**: Collect all responses where `msg_count > 0` or `mention_count > 0`. This provides a comprehensive list of all conversations with unread messages.

### Step 3: Check Thread Unreads

The process for threads is different and relies on a specific tool. **Do not trust the team-level summary for thread information.**

-   **Get User's Threads**: The only reliable method is to fetch the user's followed threads for a specific team. This call supports pagination.
    ```
    tool: get_user_threads(user_id=<user_id>, team_id=<team_id>, page=0, per_page=20)
    ```
    The response will contain a list of `threads`, and each thread object will have `unread_replies` and `unread_mentions` fields.
-   **Pagination**: The `get_user_threads` tool is paginated. Use the `page` parameter to fetch subsequent sets of threads. The `per_page` parameter is set to a default of 20 for manageable responses.

### Step 4: Mark Items as Read

-   **Marking Threads as Read**: To mark all of a user's followed threads within a team as read, use the following tool.
    ```
    tool: update_threads_read_for_user(user_id=<user_id>, team_id=<team_id>)
    ```
    **Note**: There is currently no MCP tool available to mark individual channels as read.

---

# How to Work With Users

This section describes the process for finding users and interacting with them.

## Finding Users

There are two primary methods for finding a user: searching by a general term (name, username, etc.) or getting them directly by their unique username.

-   **Search by Term**: Use the `search_users` tool to find users matching a specific term. This is useful when you have a full name but not a username.
    ```
    tool: search_users(term="<full_name_or_username>")
    ```
-   **Get by Username**: If you know the exact username, you can retrieve the user's profile directly.
    ```
    tool: get_user_by_username(username="<username>")
    ```

## Finding a Direct Message (DM) Channel

To find the channel ID for a direct message conversation between two users, follow these steps:

1.  **Get User IDs**: Ensure you have the user IDs for both users. Get the current user's ID and the other user's ID using the methods described above.
    ```
    tool: get_user(user_id="me")
    tool: get_user_by_username(username="<other_user_username>")
    ```
2.  **Get All Channels**: Fetch the current user's complete list of channels.
    ```
    tool: get_channels_for_user(user_id="me")
    ```
3.  **Identify the DM Channel**: A direct message channel between two users has a unique name format: `{user_id_1}__{user_id_2}`. The order of the IDs can vary. Iterate through the channel list, filter for channels of type `'D'`, and find the one whose `name` matches either of the two possible combinations of the user IDs. The `id` field of that channel object is the DM channel ID.

---

# Get Latest User Threads

This section outlines a streamlined process to quickly view a user's most recent threads, which is useful for a quick overview without the complexity of the full unread message retrieval process.

## The Process

1.  **Get User ID**: First, get the current user's ID to identify them.
    ```
    tool: get_user(user_id="me")
    ```
2.  **Get User's Teams**: Find out which teams the user belongs to. The API may return a single object if the user is in only one team, or a list if they are in multiple.
    ```
    tool: get_teams_for_user(user_id=<user_id>)
    ```
3.  **Fetch Threads for Each Team**: For each team ID obtained, fetch the list of threads the user is following. You can control the number of threads returned using the `per_page` parameter.
    ```
    tool: get_user_threads(user_id=<user_id>, team_id=<team_id>, per_page=10)
    ```
4.  **Display Thread Content (Optional)**: If the user wants to see the content of a specific thread, use its ID to fetch the full post list.
    ```
    tool: get_post_thread(post_id=<thread_id>)
    ```

This approach is a practical shortcut for users who just want a quick look at their recent activity, unlike the exhaustive process for finding every single unread message.

---

# How to Conduct Research

This section provides a systematic process for conducting research on a specific topic within Mattermost. This is not about finding unread messages, but about deep-diving into a subject to find root causes, explanations, and historical context.

## The Problem

Finding specific, nuanced information requires more than a simple keyword search. A single search can return dozens of irrelevant posts, alerts, and casual mentions. A structured research process is necessary to filter out the noise and extract meaningful insights from relevant conversations.

## The Process

The research workflow involves progressively narrowing your focus from a broad search to specific, information-rich threads.

1.  **Identify the Scope**: Determine which team to search in.
2.  **Perform an Initial Search**: Run a broad search with a limited result set to get a feel for the landscape.
3.  **Analyze Initial Results**: Identify promising posts and threads that seem to contain substantive discussion.
4.  **Deep-Dive into Threads**: Fetch the full content of the most relevant threads to understand the complete context.
5.  **Synthesize and Report**: Consolidate the findings into a coherent summary.

---

### Step 1: Identify the Scope

Before searching, you must know *where* to search.

-   **Get Teams**: If you are unsure which team is relevant, get a list of all teams the user belongs to.
    ```
    tool: get_teams_for_user(user_id="me")
    ```

### Step 2: Perform an Initial Search

Start with a broad search, but limit the number of results to avoid being overwhelmed.

-   **Search Posts with a Limit**: Use the `search_posts` tool with your keywords. The `per_page` parameter is critical here; a value of 20 is a good starting point.
    ```
    tool: search_posts(team_id=<team_id>, terms="<your_search_terms>", per_page=20)
    ```

### Step 3: Analyze Initial Results

The goal of this step is to identify which of the search results are worth a deeper look.

-   **Review Post Content**: Look through the `message` field of each post in the search results.
-   **Identify Key Posts**: Pay attention to posts that contain detailed explanations, links to documentation (like Confluence or Jira), or are part of a long reply chain (`reply_count > 0`). These are strong indicators of a substantive conversation. Note the `id` of these key posts.

### Step 4: Deep-Dive into Threads

Once you have identified key posts, retrieve their entire threads to see the full conversation.

-   **Get Post Thread**: For each promising post ID you identified, use the `get_post_thread` tool.
    ```
    tool: get_post_thread(post_id=<post_id>)
    ```
    This will return all the posts in that thread, allowing you to follow the discussion from beginning to end.

### Step 5: Synthesize and Report

After analyzing the relevant threads, consolidate your findings.

-   **Extract Key Information**: Pull out direct quotes, links, and conclusions from the threads.
-   **Formulate a Summary**: Write a clear, concise report that explains the issue, its context, and the resolution or current status, supported by the evidence you gathered.

This structured approach ensures that your research is thorough and that your conclusions are based on a complete understanding of the available information, rather than a superficial keyword match.
