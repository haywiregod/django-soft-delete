from django.db import models
from django.utils import timezone
from django.contrib.auth.models import UserManager


class SoftDeleteQuerySet(models.QuerySet):

    def soft_delete(self):
        try:
            self.deleted_item_pks = list(self.only("pk").values_list("pk", flat=True))
            self.update(deleted_at=timezone.now())
        except Exception as e:
            self.deleted_item_pks = []
            raise e

    def restore(self, use_manager: models.Manager):
        if hasattr(self, "deleted_item_pks") and self.deleted_item_pks:
            use_manager.filter(pk__in=self.deleted_item_pks).update(deleted_at=None)
            self.deleted_item_pks = []

    def delete(self, delete_permanently: bool = False, *args, **kwargs):
        if delete_permanently == True:
            return super().delete(*args, **kwargs)
        self.soft_delete()


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

    def soft_delete(self):
        self.deleted_at = timezone.now()
        self.save()

    def delete(self, delete_permanently: bool = False, *args, **kwargs):
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
        self.soft_delete()

    def restore(self):
        self.deleted_at = None
        self.save()

    class Meta:
        abstract = True
