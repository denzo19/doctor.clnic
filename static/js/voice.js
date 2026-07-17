function startVoice() {
    if (!('webkitSpeechRecognition' in window)) {
        alert("Speech recognition is not supported in this browser. Please use Google Chrome or Microsoft Edge.");
        return;
    }

    const recognition = new webkitSpeechRecognition();
    recognition.lang = "en-US";
    recognition.continuous = false;
    recognition.interimResults = false;

    recognition.onresult = function(event) {
        const spokenText = event.results[0][0].transcript;
        document.getElementById("voice_text").value = spokenText;
    };

    recognition.onerror = function(event) {
        alert("Voice recognition error: " + event.error);
    };

    recognition.start();
}
