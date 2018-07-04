$(function() {

    $.ajaxSetup({
        beforeSend: function(xhr, settings) {
            if (!csrfSafeMethod(settings.type) && !this.crossDomain) {
                xhr.setRequestHeader("X-CSRFToken", csrftoken);
            }
        }
    });

    // Correct form validation scrolling
    var navbar = $('#nav-bar');
    $( "form" ).each( function( index, element ){

        // Listen on all inputs
        $( element ).find(':input').on('invalid', function (event) {
            var input = $(this);

            // the first invalid element in the form
            var first = $( element ).find(':invalid').first();

            $(this).addClass('has-error');

            // only handle if this is the first invalid input
            if (input[0] === first[0]) {

                // height of the nav bar plus some padding
                var navbarHeight = navbar.height() + 50;

                // the position to scroll to (accounting for the navbar)
                var elementOffset = input.offset().top - navbarHeight;

                // the current scroll position (accounting for the navbar)
                var pageOffset = window.pageYOffset - navbarHeight;

                // don't scroll if the element is already in view
                if (elementOffset > pageOffset && elementOffset < pageOffset + window.innerHeight) {
                    return true
                }

                // note: avoid using animate, as it prevents the validation message displaying correctly
                $('html,body').scrollTop(elementOffset)
            }
        })
    });

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
    })

});

// using jQuery
function getCookie(name) {
    var cookieValue = null;
    if (document.cookie && document.cookie !== '') {
        var cookies = document.cookie.split(';');
        for (var i = 0; i < cookies.length; i++) {
            var cookie = jQuery.trim(cookies[i]);
            // Does this cookie string begin with the name we want?
            if (cookie.substring(0, name.length + 1) === (name + '=')) {
                cookieValue = decodeURIComponent(cookie.substring(name.length + 1));
                break;
            }
        }
    }
    return cookieValue;
}
var csrftoken = getCookie('csrftoken');

function csrfSafeMethod(method) {
    // these HTTP methods do not require CSRF protection
    return (/^(GET|HEAD|OPTIONS|TRACE)$/.test(method));
}

function notify(type, message, icon) {
    $.notify({
        // options
        icon: 'glyphicon glyphicon-' + icon,
        message: message,
    },{
        // settings
        type: type,
        allow_dismiss: true,
        newest_on_top: false,
        showProgressbar: false,
        placement: {
            from: "top",
            align: "center"
        },
        offset: {
            x: 0,
            y: 80
        },
        spacing: 10,
        z_index: 1031,
        delay: 2000,
        timer: 500,
        animate: {
            enter: 'animated fadeInDown',
            exit: 'animated fadeOutUp'
        }
    });
}