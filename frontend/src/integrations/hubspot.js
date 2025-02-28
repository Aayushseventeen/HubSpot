import axios from "axios";
import { useState } from "react";

export const HubSpotIntegration = ({ user, org, integrationParams, setIntegrationParams }) => {
    const [authUrl, setAuthUrl] = useState(null);
    const [contacts, setContacts] = useState([]);

    // Step 1: Get HubSpot OAuth URL
    const authorizeHubSpot = async () => {
        try {
            const response = await axios.get(`http://localhost:8000/hubspot/authorize?user_id=${user}&org_id=${org}`);
            setAuthUrl(response.data.auth_url);
            window.location.href = response.data.auth_url;
        } catch (error) {
            console.error("Error getting auth URL:", error);
        }
    };

    // Step 2: Fetch Contacts from HubSpot
    const fetchContacts = async () => {
        try {
            const response = await axios.get(`http://localhost:8000/hubspot/items?user_id=${user}&org_id=${org}`);
            setContacts(response.data.contacts || []);
        } catch (error) {
            console.error("Error fetching contacts:", error);
        }
    };

    return (
        <div>
            <h2>HubSpot Integration</h2>
            <p><strong>User:</strong> {user}</p>  {/* ✅ Show user name */}
            <p><strong>Organization:</strong> {org}</p>  {/* ✅ Show organization name */}

            {/* Step 1: Show OAuth URL */}
            <button onClick={authorizeHubSpot}>Connect HubSpot</button>
            {authUrl && <a href={authUrl} target="_blank" rel="noopener noreferrer">Authorize HubSpot</a>}

            {/* Step 2: Fetch Data */}
            <button onClick={fetchContacts}>Fetch Contacts</button>

            {/* Display contacts */}
            <ul>
                {contacts.map((contact) => (
                    <li key={contact.id}>
                        {contact.first_name} {contact.last_name} - {contact.email}
                    </li>
                ))}
            </ul>
        </div>
    );
};
