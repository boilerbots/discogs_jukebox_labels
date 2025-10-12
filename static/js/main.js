document.addEventListener("DOMContentLoaded", () => {
    const socket = io();

    const folderNameInput = document.getElementById("folder-name");
    const setFolderButton = document.getElementById("set-folder-button");
    const decrementSlotButton = document.getElementById("decrement-slot");
    const incrementSlotButton = document.getElementById("increment-slot");
    const slotCounterSpan = document.getElementById("slot-counter");
    const statusDiv = document.getElementById("status");
    const startButton = document.getElementById("start-identification-button");
    const resultsList = document.getElementById("results-list");

    let folderId = null;
    let slotCounter = 0;
    let mediaRecorder;
    let audioChunks = [];
    let stream;

    // Event Listeners
    folderNameInput.addEventListener("keydown", (event) => {
        if (event.key === "Enter") {
            setFolderButton.click();
        }
    });

    setFolderButton.addEventListener("click", () => {
        const folderName = folderNameInput.value.trim();
        if (folderName) {
            socket.emit("set_folder", folderName);
        }
    });

    decrementSlotButton.addEventListener("click", () => {
        if (slotCounter > 1) {
            slotCounter--;
            slotCounterSpan.textContent = slotCounter;
        }
    });

    incrementSlotButton.addEventListener("click", () => {
        slotCounter++;
        slotCounterSpan.textContent = slotCounter;
    });

    startButton.addEventListener("click", async () => {
        startButton.disabled = true;
        resultsList.innerHTML = "";

        try {
            stream = await navigator.mediaDevices.getUserMedia({ audio: true });
            mediaRecorder = new MediaRecorder(stream);

            mediaRecorder.ondataavailable = (event) => {
                audioChunks.push(event.data);
            };

            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: "audio/wav" });
                socket.emit("identify", audioBlob);
                audioChunks = [];
                statusDiv.textContent = "Processing audio...";
                stream.getTracks().forEach(track => track.stop());
            };

            mediaRecorder.start();
            statusDiv.textContent = "Recording for 10 seconds...";

            setTimeout(() => {
                if (mediaRecorder.state === "recording") {
                    mediaRecorder.stop();
                }
            }, 10000);

        } catch (err) {
            statusDiv.textContent = "Error accessing microphone.";
            console.error("Error accessing microphone:", err);
            if (stream) {
                stream.getTracks().forEach(track => track.stop());
            }
            startButton.disabled = false;
        }
    });

    // Socket.IO Handlers
    socket.on("connect", () => {
        console.log("Connected to server");
    });

    socket.on("folder_set", (data) => {
        folderId = data.folder_id;
        folderNameInput.disabled = true;
        setFolderButton.disabled = true;
        startButton.disabled = false;
        statusDiv.textContent = `Using folder '${data.folder_name}'.`;
    });

    socket.on("status", (data) => {
        statusDiv.textContent = data.message;
    });

    socket.on("search_results", (data) => {
        resultsList.innerHTML = "";
        if (data.releases && data.releases.length > 0) {
            statusDiv.textContent = `Found ${data.releases.length} releases.`;
            data.releases.forEach(release => {
                const li = document.createElement("li");
                li.innerHTML = `
                    <span>${release.title} (${release.country} - ${release.year})</span>
                    <button class="add-release-button" data-release-id="${release.id}">Add</button>
                `;
                resultsList.appendChild(li);
            });

            document.querySelectorAll(".add-release-button").forEach(button => {
                button.addEventListener("click", (event) => {
                    const releaseId = event.target.getAttribute("data-release-id");
                    socket.emit("add_release", { 
                        folder_id: folderId, 
                        release_id: releaseId, 
                        slot: slotCounter 
                    });
                });
            });
        }/* else {
            resultsList.innerHTML = "<li>No results found.</li>";
            statusDiv.textContent = "No matching releases found.";
        }*/
        startButton.disabled = false;
    });

    socket.on("release_added", (data) => {
        const addedButton = document.querySelector(`.add-release-button[data-release-id="${data.release_id}"]`);
        if (addedButton) {
            addedButton.textContent = "Added";
            addedButton.disabled = true;
        }
        slotCounter++;
        slotCounterSpan.textContent = slotCounter;
        statusDiv.textContent = `Release added to folder.`;
    });

    socket.on("error", (data) => {
        statusDiv.textContent = `Error: ${data.message}`;
        startButton.disabled = false;
    });
});
