from django.db import models, transaction
from django.utils import timezone
from django.contrib.auth.models import UserManager


class SoftDeleteQuerySet(models.QuerySet):

    @transaction.atomic
    def soft_delete(self, cascade_related=True):
        try:
            self.deleted_item_pks = list(self.only("pk").values_list("pk", flat=True))
            self.update(deleted_at=timezone.now())

            if cascade_related:
                # Soft delete related objects (cascade)
                for obj in self:  # Iterate through queryset objects
                    obj: SoftDeleteModel
                    obj._cascade_soft_delete(cascade_related=cascade_related)
        except Exception as e:
            self.deleted_item_pks = []
            raise e

    @transaction.atomic
    def restore(self, use_manager: models.Manager, restore_cascaded=True):
        if hasattr(self, "deleted_item_pks") and self.deleted_item_pks:
            use_manager.filter(pk__in=self.deleted_item_pks).update(deleted_at=None)

            if restore_cascaded:
                for obj in use_manager.filter(pk__in=self.deleted_item_pks):
                    obj: SoftDeleteModel
                    obj._cascade_restore(
                        use_manager=use_manager, restore_cascaded=restore_cascaded
                    )

            self.deleted_item_pks = []

    @transaction.atomic
    def delete(
        self, delete_permanently: bool = False, cascade_related=True, *args, **kwargs
    ):
        if delete_permanently == True:
            return super().delete(*args, **kwargs)
        self.soft_delete(cascade_related=cascade_related)


class SoftDeleteManager(models.Manager):
    def get_queryset(self):
        qs = SoftDeleteQuerySet(self.model, using=self._db).filter(
            deleted_at__isnull=True
        )
        return qs


class UserSoftDeleteManager(UserManager):
    """
    AbstractUser model uses UserManager as it's default model manager which has
    more functionalities than models.Manager, so can't use SoftDeleteManager.
    This manager is used to soft delete AbstractUser objects.

    When creating a User model, use this manager in it to have soft delete
    features
    """

    def get_queryset(self):
        qs = SoftDeleteQuerySet(self.model, using=self._db).filter(
            deleted_at__isnull=True
        )
        return qs


class SoftDeleteModel(models.Model):
    """
    This class definition is an abstract base class for Django models that provides a soft deletion mechanism.
    Note: that this class has two managers: `objects` (which filters out soft-deleted objects)
    and `all_objects` (which returns all objects, including soft-deleted ones).
    """

    deleted_at = models.DateTimeField(default=None, null=True, blank=True)
    objects = SoftDeleteManager()
    all_objects = models.Manager()

    @transaction.atomic
    def soft_delete(self, cascade_related=True):
        self.deleted_at = timezone.now()
        self.save()
        if cascade_related:
            self._cascade_soft_delete(cascade_related=cascade_related)

    @transaction.atomic
    def delete(
        self, delete_permanently: bool = False, cascade_related=True, *args, **kwargs
    ):
        """
        Soft Deletes the object from the database.
        Note: Cascade is not handled.

        Args:
            delete_permanently (bool): If True, the object is permanently deleted.
                Otherwise, it is soft-deleted. Defaults to False.

        Returns:
            None
        """

        if delete_permanently == True:  # should be True and not any other truthy value
            return super().delete(*args, **kwargs)
        self.soft_delete(cascade_related=cascade_related)

    @transaction.atomic
    def restore(self, restore_cascaded=True, use_manager: models.Manager = None):
        self.deleted_at = None
        self.save()
        if restore_cascaded:
            if not use_manager:
                raise ValueError(
                    "use_manager is required when restore_cascaded is True"
                )
            self._cascade_restore(
                use_manager=use_manager, restore_cascaded=restore_cascaded
            )

    def _cascade_soft_delete(self, cascade_related: bool):
        """Find related objects and soft delete them."""
        for relation in self._meta.related_objects:
            print(f"cascading related object: {relation}")
            if relation.on_delete == models.CASCADE:  # Only process CASCADE relations
                related_name = relation.get_accessor_name()
                related_manager = getattr(self, related_name, None)

                if related_manager and hasattr(related_manager, "all"):
                    related_queryset = related_manager.all()
                    if isinstance(related_queryset, SoftDeleteQuerySet):
                        related_queryset.soft_delete(cascade_related=cascade_related)

    def _cascade_restore(self, use_manager: models.Manager, restore_cascaded: bool):
        """Find related objects and restore them."""
        for relation in self._meta.related_objects:
            print(f"restoring cascaded related object: {relation}")
            if relation.on_delete == models.CASCADE:
                related_name = relation.get_accessor_name()
                related_manager = getattr(self, related_name, None)

                if related_manager and hasattr(related_manager, "all"):
                    related_queryset = related_manager.all()
                    if isinstance(related_queryset, SoftDeleteQuerySet):
                        related_queryset.restore(
                            use_manager=use_manager, restore_cascaded=restore_cascaded
                        )

    class Meta:
        abstract = True
