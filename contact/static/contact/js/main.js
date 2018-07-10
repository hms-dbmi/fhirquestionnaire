$(function() {

    // AJAX for posting
    $(".contact-form-button").on('click', function () {
        console.log("Loading contact form");
        $.ajax({
            type: 'GET',
            url: '/contact/',
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
        console.log("Sending contact form");
        $.ajax({
            url : "/contact/",
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