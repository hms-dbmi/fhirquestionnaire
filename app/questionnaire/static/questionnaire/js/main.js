$(function() {

    // Add a handler that triggers on assignment as well as on the specified event
    jQuery.fn.nowAndOn = function (event, handler) {
        this.each(function () {
            handler.call(this);
        });
        this.bind(event, handler);
        return this;
    };

    $('[data-details!=""]').nowAndOn('change', function (){

        // Get the ID
        var checkbox = $(this);
        var _name = $(this).data('details');
        if( ! _name ) return;

        // See if checked
        var checked = this.checked;

        // Get this value
        var value = $(this).val();

        // Check for a detail input
        var enabledWhen = _name + '\=' + value;
        $('[data-enabled-when="' + enabledWhen + '"]').each(function() {

            // Get the element
            var input = $(this);

            // Move the element
            if(checked) {

                // Place the element next to the input
                $(checkbox).parent().parent().append($(this));

                // Show it
                $(input).show();

                // Mark it as required
                $(input).attr('required', 'required');
            } else {

                // Show it
                $(input).hide();

                // Clear value
                $(input).removeAttr('value');
                $(input).val('');

                // Set it as non-required
                $(input).removeAttr('required');
            }

        });
    });
});