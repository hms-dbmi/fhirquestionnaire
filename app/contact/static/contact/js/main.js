$(function() {

    // AJAX for posting
    $(".contact-form-button").on('click', function () {
        console.log("Loading contact form");
        $.ajax({
            type: 'GET',
            url: $('#contact-form-modal').data( 'contact-url' ),
            success: function (data, textStatus, jqXHR) {
                $('#contact-form-modal').html(data);
                $('#contact-form-modal').modal('show');
            },
            error : function(xhr,errmsg,err) {
                console.log(xhr.status + ": " + xhr.responseText);
            }
        });
        return false;
    });

    $('#contact-form-modal').on('submit', '#contact-form', function() {
        console.log("submit: contact-form");

        // Ensure reCAPTCHA is completed
        if (typeof grecaptcha !== 'undefined') {

            // Only submit form if RECAPTCHA is filled out
            if(grecaptcha.getResponse().length === 0) {
                console.log("Contact-form-recaptcha: " + grecaptcha.getResponse());
                return false;
            }
        } else {
            console.log("Contact-form-recaptcha: DISABLED");
        }

        console.log("Sending contact form");
        $.ajax({
            url : $('#contact-form-modal').data( 'contact-url' ),
            type : "POST",
            data: $(this).serialize(),
            context: this,
            success : function(json) {
                $('#contact-form-modal').modal('hide');
                notify('success', 'Thanks, your message has been submitted!', 'thumbs-up');
            },
            error : function(xhr,errmsg,err) {
                $('#contact-form-modal').modal('hide');
                notify('danger', 'Something happened, please try again', 'exclamation-sign');
                console.log(xhr.status + ": " + xhr.responseText);
            }
        });
        return false;
    });

    $('#contact-form-modal').on('hidden.bs.modal', function (e) {
      // do something...
    });

});

function recaptchaCallback() {

    // Enable the submit button
    $('#contact-form-submit').prop("disabled", false);
}
