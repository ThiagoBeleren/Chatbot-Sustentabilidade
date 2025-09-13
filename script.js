const button = document.getElementsByClassName('animated-button');
const botmessage = document.getElementById('botmessage');
const usermessage = document.getElementById('usermessage');

function sendMessage() {
    const inputField = document.querySelector('.input');
    const userText = inputField.value;
    usermessage.innerHTML = userText;
    inputField.value = '';  
    botmessage.innerHTML = "Processando...";
    // Simulate bot response after a delay
    setTimeout(() => {
        botmessage.innerHTML = "Esta é uma resposta simulada do bot.";
    }, 2000);
    return false; // Prevent form submission
}
for (let i = 0; i < button.length; i++) {
    button[i].addEventListener('click', sendMessage);
}


